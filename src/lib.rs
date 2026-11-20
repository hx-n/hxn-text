//! Runtime-neutral font and text data. Applications own loading, drawing and GPU textures.
use std::{fmt, sync::Arc};
mod engine;
mod font;

hxn::package!("hxn.text");

#[hxn::data]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TextErrorCode {
    InvalidFont,
    InvalidOptions,
    FontUnavailable,
    AtlasFull,
    LimitExceeded,
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct TextError {
    pub code: TextErrorCode,
    pub message: String,
}
impl fmt::Display for TextError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}
impl TextError {
    pub(crate) fn new(code: TextErrorCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}

#[hxn::data]
#[derive(Clone, Copy, Debug)]
pub struct FontOptions {
    #[hxn(default)]
    pub face_index: u32,
    #[hxn(default = "FontOptions::regular")]
    pub weight: u16,
}
impl FontOptions {
    pub fn regular() -> u16 {
        400
    }
}
impl Default for FontOptions {
    fn default() -> Self {
        Self {
            face_index: 0,
            weight: 400,
        }
    }
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct FontMetrics {
    pub units_per_em: u32,
    pub ascent: f32,
    pub descent: f32,
    pub line_gap: f32,
    pub cap_height: f32,
    pub x_height: f32,
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct ShapedGlyph {
    pub glyph_id: u32,
    /// UTF-8 byte offset of the source cluster, including for right-to-left text.
    pub cluster: u32,
    pub x_advance: f32,
    pub y_advance: f32,
    pub x_offset: f32,
    pub y_offset: f32,
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct GlyphRun {
    pub glyphs: Vec<ShapedGlyph>,
    pub width: f32,
    pub size: f32,
}

#[hxn::data]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AtlasKind {
    Coverage,
    Color,
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct GlyphBitmap {
    pub kind: AtlasKind,
    pub width: u32,
    pub height: u32,
    pub stride: u32,
    pub bearing_x: i32,
    pub bearing_y: i32,
    pub pixels: Vec<u8>,
}

#[hxn::data]
#[derive(Clone, Copy, Debug)]
pub enum TextAlignment {
    Left,
    Center,
    Right,
}

#[hxn::data]
#[derive(Clone, Copy, Debug)]
pub enum TextWrap {
    None,
    Word,
    Character,
}

#[hxn::data]
#[derive(Clone, Copy, Debug)]
pub struct TextOptions {
    #[hxn(default = "TextOptions::default_size")]
    pub size: f32,
    /// Zero disables wrapping to a maximum width.
    #[hxn(default)]
    pub max_width: f32,
    #[hxn(default = "TextOptions::default_line_height")]
    pub line_height: f32,
    #[hxn(default)]
    pub letter_spacing: f32,
    #[hxn(default = "TextOptions::default_alignment")]
    pub alignment: TextAlignment,
    #[hxn(default = "TextOptions::default_wrap")]
    pub wrap: TextWrap,
    /// Device pixels per logical pixel, including a stable application zoom.
    #[hxn(default = "TextOptions::default_scale")]
    pub scale: f32,
    #[hxn(default)]
    pub subpixel: bool,
}
impl TextOptions {
    pub fn default_alignment() -> TextAlignment {
        TextAlignment::Left
    }
    pub fn default_wrap() -> TextWrap {
        TextWrap::Word
    }
    pub fn default_size() -> f32 {
        16.0
    }
    pub fn default_line_height() -> f32 {
        1.2
    }
    pub fn default_scale() -> f32 {
        1.0
    }
}
impl Default for TextOptions {
    fn default() -> Self {
        Self {
            size: 16.0,
            max_width: 0.0,
            line_height: 1.2,
            letter_spacing: 0.0,
            alignment: TextAlignment::Left,
            wrap: TextWrap::Word,
            scale: 1.0,
            subpixel: false,
        }
    }
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct TextGlyph {
    /// Logical pixel bounds, relative to the text origin.
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
    /// Atlas pixel coordinates. Normalize against the texture's current dimensions when drawing.
    pub atlas_x: u32,
    pub atlas_y: u32,
    pub atlas_width: u32,
    pub atlas_height: u32,
    pub kind: AtlasKind,
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct PreparedText {
    pub glyphs: Vec<TextGlyph>,
    pub width: f32,
    pub height: f32,
    pub ascent: f32,
    pub descent: f32,
    /// Compare with TextEngine.generation before reusing atlas coordinates.
    pub generation: u32,
}

#[hxn::data]
#[derive(Clone, Debug)]
pub struct AtlasUpdate {
    pub kind: AtlasKind,
    pub revision: u32,
    pub generation: u32,
    pub width: u32,
    pub height: u32,
    pub x: u32,
    pub y: u32,
    pub patch_width: u32,
    pub patch_height: u32,
    /// Tightly packed rows: patch_width for coverage, four times it for straight RGBA.
    pub stride: u32,
    pub full: bool,
    pub pixels: Vec<u8>,
}

/// Immutable font bytes and selected face. Engines retain fonts they prepare.
#[hxn::interface(shared, weighed)]
pub struct Font {
    inner: Arc<font::OwnedFont>,
}

#[hxn::methods]
impl Font {
    /// Copies and validates TTF, OpenType, collection or WOFF2 bytes.
    pub fn new(bytes: &[u8], options: FontOptions) -> Result<Self, TextError> {
        Ok(Self {
            inner: Arc::new(font::OwnedFont::decode(bytes, options)?),
        })
    }
    /// Platform font lookup. Browser applications supply their own font bytes.
    #[hxn(blocking)]
    pub fn system(family: &str, weight: u16, italic: bool) -> Result<Self, TextError> {
        Ok(Self {
            inner: Arc::new(font::OwnedFont::system(family, weight, italic)?),
        })
    }
    pub fn family(&self) -> String {
        self.inner.face.family_name().to_owned()
    }
    pub fn face_index(&self) -> u32 {
        self.inner.face.face_index()
    }
    pub fn metrics(&self, size: f32) -> Result<FontMetrics, TextError> {
        self.inner.metrics(size)
    }
    pub fn supports(&self, text: &str) -> bool {
        text.chars()
            .all(|c| c.is_whitespace() || self.inner.face.has_glyph(c))
    }
    /// Shapes one segment. Clusters are byte offsets, not Haxe string indexes.
    pub fn shape(&self, text: &str, size: f32) -> Result<GlyphRun, TextError> {
        self.inner.shape(text, size)
    }
    pub fn rasterize(
        &self,
        glyph_id: u32,
        size: f32,
        kind: AtlasKind,
    ) -> Result<GlyphBitmap, TextError> {
        self.inner.rasterize(glyph_id, size, kind)
    }
}

/// A CPU text engine with independent glyph atlases. It never draws or owns a GPU resource.
#[hxn::interface(weighed)]
pub struct TextEngine {
    inner: engine::Engine,
}

#[hxn::methods]
impl TextEngine {
    pub fn new() -> Self {
        Self {
            inner: engine::Engine::new(),
        }
    }
    pub fn prepare(
        &mut self,
        font: &Font,
        text: &str,
        options: TextOptions,
    ) -> Result<PreparedText, TextError> {
        self.inner.prepare(Arc::clone(&font.inner), text, options)
    }
    /// Pass each texture consumer's last revision, or zero for a complete snapshot.
    pub fn atlas(&mut self, kind: AtlasKind, seen_revision: u32) -> Result<AtlasUpdate, TextError> {
        self.inner.atlas(kind, seen_revision)
    }
    pub fn generation(&self) -> u32 {
        self.inner.generation()
    }
    /// Invalidates prepared atlas coordinates while retaining registered fonts.
    pub fn clear(&mut self) -> Result<(), TextError> {
        self.inner.clear()
    }
    /// Releases retained fonts and caches, and invalidates prepared atlas coordinates.
    pub fn clear_fonts(&mut self) -> Result<(), TextError> {
        self.inner.clear_fonts()
    }
}
impl Default for TextEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests;
