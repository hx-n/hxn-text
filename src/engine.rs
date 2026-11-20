use crate::{
    AtlasKind, AtlasUpdate, PreparedText, TextAlignment, TextError, TextErrorCode, TextGlyph,
    TextOptions, TextWrap,
    font::{self, OwnedFont},
};
use blinc_text::{FontRegistry, GenericFont, LayoutOptions, SubpixelX, TextAnchor, TextRenderer};
use std::{
    collections::{HashMap, VecDeque},
    num::NonZeroU8,
    sync::{Arc, Mutex},
};

type Rect = (u32, u32, u32, u32);
struct Change {
    revision: u32,
    rect: Rect,
    dimensions: (u32, u32),
}
#[derive(Default)]
struct History {
    revision: u32,
    changes: VecDeque<Change>,
}

pub(crate) struct Engine {
    renderer: TextRenderer,
    registry: Arc<Mutex<FontRegistry>>,
    fonts: HashMap<u64, Arc<OwnedFont>>,
    histories: [History; 2],
    generation: u32,
    weight: hxn::Weight,
}
impl Engine {
    pub fn new() -> Self {
        let registry = Arc::new(Mutex::new(FontRegistry::new()));
        let renderer = TextRenderer::with_shared_registry(Arc::clone(&registry));
        let mut this = Self {
            renderer,
            registry,
            fonts: HashMap::new(),
            histories: Default::default(),
            generation: 1,
            weight: hxn::Weight::default(),
        };
        this.account();
        this
    }
    fn account(&mut self) {
        self.weight
            .set(self.renderer.atlas_pixels().len() + self.renderer.color_atlas_pixels().len());
    }
    pub fn generation(&self) -> u32 {
        self.generation
    }
    fn advance_generation(&mut self) -> Result<(), TextError> {
        self.generation = self.generation.checked_add(1).ok_or_else(|| {
            TextError::new(
                TextErrorCode::LimitExceeded,
                "text engine generation exhausted",
            )
        })?;
        Ok(())
    }
    pub fn clear(&mut self) -> Result<(), TextError> {
        self.advance_generation()?;
        self.renderer.clear();
        self.account();
        Ok(())
    }
    pub fn clear_fonts(&mut self) -> Result<(), TextError> {
        let generation = self.generation.checked_add(1).ok_or_else(|| {
            TextError::new(
                TextErrorCode::LimitExceeded,
                "text engine generation exhausted",
            )
        })?;
        let revisions = [self.histories[0].revision, self.histories[1].revision];
        *self = Self::new();
        self.generation = generation;
        for (history, revision) in self.histories.iter_mut().zip(revisions) {
            history.revision = revision;
        }
        Ok(())
    }
    pub fn prepare(
        &mut self,
        font: Arc<OwnedFont>,
        value: &str,
        options: TextOptions,
    ) -> Result<PreparedText, TextError> {
        font::size(options.size)?;
        font::text(value)?;
        if !options.scale.is_finite()
            || !(0.0625..=16.0).contains(&options.scale)
            || !options.max_width.is_finite()
            || !(0.0..=1_000_000.0).contains(&options.max_width)
            || !options.line_height.is_finite()
            || !(0.25..=10.0).contains(&options.line_height)
            || !options.letter_spacing.is_finite()
            || options.letter_spacing.abs() > 256.0
            || options.size * options.scale > 256.0
        {
            return Err(TextError::new(
                TextErrorCode::InvalidOptions,
                "invalid text scale, width, line height, spacing or raster size",
            ));
        }
        let id = font.face.id();
        let name = format!("hxn-text-{id}");
        if !self.fonts.contains_key(&id) {
            if self.fonts.len() >= 256 {
                return Err(TextError::new(
                    TextErrorCode::LimitExceeded,
                    "text engine retains at most 256 faces; use clearFonts to release them",
                ));
            }
            self.registry
                .lock()
                .map_err(|_| font::failed("font registry is unavailable"))?
                .register_face(name.clone(), Arc::clone(&font.face));
            self.fonts.insert(id, Arc::clone(&font));
        }
        let scale = options.scale;
        let layout = LayoutOptions {
            max_width: (options.max_width > 0.0).then_some(options.max_width * scale),
            alignment: match options.alignment {
                TextAlignment::Left => blinc_text::TextAlignment::Left,
                TextAlignment::Center => blinc_text::TextAlignment::Center,
                TextAlignment::Right => blinc_text::TextAlignment::Right,
            },
            anchor: TextAnchor::Top,
            line_break: match options.wrap {
                TextWrap::None => blinc_text::LineBreakMode::None,
                TextWrap::Word => blinc_text::LineBreakMode::Word,
                TextWrap::Character => blinc_text::LineBreakMode::Character,
            },
            line_height: options.line_height,
            letter_spacing: options.letter_spacing * scale,
        };
        let subpixel = options
            .subpixel
            .then(|| SubpixelX::new(NonZeroU8::new(3).unwrap(), 0.0));
        let prepared = self.renderer.prepare_text_subpixel(
            value,
            options.size * scale,
            [1.0; 4],
            &layout,
            Some(&name),
            GenericFont::SansSerif,
            400,
            false,
            subpixel,
        );
        self.account();
        let prepared = prepared.map_err(|e| {
            TextError::new(
                if matches!(e, blinc_text::TextError::AtlasFull) {
                    TextErrorCode::AtlasFull
                } else {
                    TextErrorCode::InvalidFont
                },
                e.to_string(),
            )
        })?;
        let glyphs = prepared
            .glyphs
            .into_iter()
            .map(|g| TextGlyph {
                x: g.bounds[0] / scale,
                y: g.bounds[1] / scale,
                width: g.bounds[2] / scale,
                height: g.bounds[3] / scale,
                atlas_x: g.uv_bounds[0] as u32,
                atlas_y: g.uv_bounds[1] as u32,
                atlas_width: (g.uv_bounds[2] - g.uv_bounds[0]) as u32,
                atlas_height: (g.uv_bounds[3] - g.uv_bounds[1]) as u32,
                kind: if g.is_color {
                    AtlasKind::Color
                } else {
                    AtlasKind::Coverage
                },
            })
            .collect();
        Ok(PreparedText {
            glyphs,
            width: prepared.width / scale,
            height: prepared.height / scale,
            ascent: prepared.ascender / scale,
            descent: prepared.descender / scale,
            generation: self.generation,
        })
    }
    pub fn atlas(&mut self, kind: AtlasKind, seen: u32) -> Result<AtlasUpdate, TextError> {
        let color = kind == AtlasKind::Color;
        let (dirty, rect, dimensions) = if color {
            (
                self.renderer.color_atlas_is_dirty(),
                self.renderer.color_atlas_dirty_rect(),
                self.renderer.color_atlas_dimensions(),
            )
        } else {
            (
                self.renderer.atlas_is_dirty(),
                self.renderer.atlas_dirty_rect(),
                self.renderer.atlas_dimensions(),
            )
        };
        let history = &mut self.histories[color as usize];
        if dirty {
            history.revision = history.revision.checked_add(1).ok_or_else(|| {
                TextError::new(TextErrorCode::LimitExceeded, "atlas revision exhausted")
            })?;
            history.changes.push_back(Change {
                revision: history.revision,
                rect: rect.unwrap_or((0, 0, dimensions.0, dimensions.1)),
                dimensions,
            });
            if history.changes.len() > 32 {
                history.changes.pop_front();
            }
            if color {
                self.renderer.mark_color_atlas_clean();
            } else {
                self.renderer.mark_atlas_clean();
            }
        }
        let changed: Vec<_> = history
            .changes
            .iter()
            .filter(|c| c.revision > seen)
            .collect();
        let incremental = seen > 0
            && seen < history.revision
            && changed.first().is_some_and(|c| c.revision == seen + 1)
            && changed.iter().all(|c| c.dimensions == dimensions);
        let full = seen != history.revision && !incremental;
        let (x, y, w, h) = if seen == history.revision {
            (0, 0, 0, 0)
        } else if incremental {
            let mut bounds = (u32::MAX, u32::MAX, 0, 0);
            for c in changed {
                bounds.0 = bounds.0.min(c.rect.0);
                bounds.1 = bounds.1.min(c.rect.1);
                bounds.2 = bounds.2.max(c.rect.0 + c.rect.2);
                bounds.3 = bounds.3.max(c.rect.1 + c.rect.3);
            }
            (bounds.0, bounds.1, bounds.2 - bounds.0, bounds.3 - bounds.1)
        } else {
            (0, 0, dimensions.0, dimensions.1)
        };
        let bpp = if color { 4 } else { 1 };
        let stride = w * bpp;
        let pixels = if color {
            self.renderer.color_atlas_pixels()
        } else {
            self.renderer.atlas_pixels()
        };
        let mut patch = vec![0; (stride * h) as usize];
        for row in 0..h {
            let from = ((y + row) * dimensions.0 + x) as usize * bpp as usize;
            let to = (row * stride) as usize;
            if let Some(source) = pixels.get(from..from + stride as usize) {
                patch[to..to + stride as usize].copy_from_slice(source);
            }
        }
        Ok(AtlasUpdate {
            kind,
            revision: history.revision,
            generation: self.generation,
            width: dimensions.0,
            height: dimensions.1,
            x,
            y,
            patch_width: w,
            patch_height: h,
            stride,
            full,
            pixels: patch,
        })
    }
}
