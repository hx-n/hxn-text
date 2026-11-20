use crate::{
    AtlasKind, FontMetrics, FontOptions, GlyphBitmap, GlyphRun, ShapedGlyph, TextError,
    TextErrorCode,
};
use blinc_text::{FontFace, GlyphRasterizer, TextShaper, font::FontData};
use std::sync::Arc;

pub(crate) const MAX_FONT_BYTES: usize = 64 * 1024 * 1024;
pub(crate) const MAX_TEXT_BYTES: usize = 64 * 1024;

pub(crate) fn size(value: f32) -> Result<(), TextError> {
    if !value.is_finite() || !(0.5..=256.0).contains(&value) {
        return Err(TextError::new(
            TextErrorCode::InvalidOptions,
            "font size must be finite and between 0.5 and 256 pixels",
        ));
    }
    Ok(())
}
pub(crate) fn text(value: &str) -> Result<(), TextError> {
    if value.len() > MAX_TEXT_BYTES {
        return Err(TextError::new(
            TextErrorCode::LimitExceeded,
            "text exceeds 64 KiB",
        ));
    }
    Ok(())
}
pub(crate) fn failed(error: impl ToString) -> TextError {
    TextError::new(TextErrorCode::InvalidFont, error.to_string())
}

pub(crate) struct FontStorage {
    pub data: FontData,
    _weight: hxn::Weight,
}
pub(crate) struct OwnedFont {
    pub face: Arc<FontFace>,
    _storage: Arc<FontStorage>,
    shaper: TextShaper,
}
impl OwnedFont {
    pub fn decode(bytes: &[u8], options: FontOptions) -> Result<Self, TextError> {
        if bytes.is_empty() || bytes.len() > MAX_FONT_BYTES {
            return Err(TextError::new(
                TextErrorCode::LimitExceeded,
                "font bytes must be nonempty and at most 64 MiB",
            ));
        }
        if !(1..=1000).contains(&options.weight) {
            return Err(TextError::new(
                TextErrorCode::InvalidOptions,
                "font weight must be between 1 and 1000",
            ));
        }
        let data = if bytes.starts_with(b"wOF2") {
            let declared = bytes
                .get(16..20)
                .and_then(|b| <[u8; 4]>::try_from(b).ok())
                .map(u32::from_be_bytes)
                .unwrap_or(0) as usize;
            if declared == 0 || declared > MAX_FONT_BYTES {
                return Err(failed("invalid or oversized WOFF2 font"));
            }
            woff2_patched::convert_woff2_to_ttf(&mut std::io::Cursor::new(bytes)).map_err(failed)?
        } else {
            bytes.to_vec()
        };
        if data.len() > MAX_FONT_BYTES {
            return Err(failed("decoded font exceeds 64 MiB"));
        }
        let length = data.len();
        let storage = Arc::new(FontStorage {
            data: FontData::from_vec(data),
            _weight: hxn::Weight::new(length),
        });
        let mut face =
            FontFace::from_font_data(storage.data.clone(), options.face_index).map_err(failed)?;
        face.set_variation_weight(options.weight);
        hxn::log::debug!(target: "hxn.text", "decoded font {} (face {}, weight {})", face.family_name(), options.face_index, options.weight);
        Ok(Self {
            face: Arc::new(face),
            _storage: storage,
            shaper: TextShaper::new(),
        })
    }
    pub fn system(family: &str, weight: u16, italic: bool) -> Result<Self, TextError> {
        if !(1..=1000).contains(&weight) || family.is_empty() || family.len() > 256 {
            return Err(TextError::new(
                TextErrorCode::InvalidOptions,
                "system font needs a family name and weight 1..1000",
            ));
        }
        if cfg!(target_family = "wasm") {
            return Err(TextError::new(
                TextErrorCode::FontUnavailable,
                "browser fonts must be loaded from application bytes",
            ));
        }
        let registry = blinc_text::global_font_registry();
        let face = registry
            .lock()
            .map_err(|_| failed("font registry is unavailable"))?
            .load_font_with_style(family, weight, italic)
            .map_err(|e| TextError::new(TextErrorCode::FontUnavailable, e.to_string()))?;
        struct SharedFace(Arc<FontFace>);
        impl AsRef<[u8]> for SharedFace {
            fn as_ref(&self) -> &[u8] {
                self.0.data()
            }
        }
        let storage = Arc::new(FontStorage {
            data: FontData::from_mapped(Arc::new(SharedFace(Arc::clone(&face)))),
            _weight: hxn::Weight::new(face.data().len()),
        });
        Ok(Self {
            face,
            _storage: storage,
            shaper: TextShaper::new(),
        })
    }
    pub fn metrics(&self, px: f32) -> Result<FontMetrics, TextError> {
        size(px)?;
        let m = self.face.metrics();
        Ok(FontMetrics {
            units_per_em: m.units_per_em.into(),
            ascent: m.ascender_px(px),
            descent: m.descender_px(px),
            line_gap: m.scale(m.line_gap, px),
            cap_height: m.scale(m.cap_height.unwrap_or(0), px),
            x_height: m.scale(m.x_height.unwrap_or(0), px),
        })
    }
    pub fn shape(&self, value: &str, px: f32) -> Result<GlyphRun, TextError> {
        size(px)?;
        text(value)?;
        let shaped = self.shaper.shape(value, &self.face, px);
        let glyphs = shaped
            .glyphs
            .iter()
            .map(|g| ShapedGlyph {
                glyph_id: g.glyph_id.into(),
                cluster: g.cluster,
                x_advance: shaped.scale(g.x_advance),
                y_advance: shaped.scale(g.y_advance),
                x_offset: shaped.scale(g.x_offset),
                y_offset: shaped.scale(g.y_offset),
            })
            .collect();
        Ok(GlyphRun {
            glyphs,
            width: shaped.width_px(),
            size: px,
        })
    }
    pub fn rasterize(&self, id: u32, px: f32, kind: AtlasKind) -> Result<GlyphBitmap, TextError> {
        size(px)?;
        if id >= self.face.glyph_count() as u32 {
            return Err(failed("glyph ID is outside this face"));
        }
        let mut raster = GlyphRasterizer::new();
        let image = match kind {
            AtlasKind::Coverage => raster.rasterize(&self.face, id as u16, px),
            AtlasKind::Color => raster.rasterize_color(&self.face, id as u16, px),
        }
        .map_err(failed)?;
        Ok(GlyphBitmap {
            kind,
            width: image.width,
            height: image.height,
            stride: image.width * if kind == AtlasKind::Color { 4 } else { 1 },
            bearing_x: image.bearing_x.into(),
            bearing_y: image.bearing_y.into(),
            pixels: image.bitmap,
        })
    }
}
