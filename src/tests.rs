use super::*;
const LATIN: &[u8] = include_bytes!("../tests/fixtures/NotoSans-Regular.ttf");
const ARABIC: &[u8] = include_bytes!("../tests/fixtures/arabic.ttf");
const INDIC: &[u8] = include_bytes!("../tests/fixtures/devanagari.ttf");
fn latin() -> Font {
    Font::new(LATIN, FontOptions::default()).unwrap()
}

#[test]
fn owned_fonts_keep_copied_bytes_and_validate_options() {
    let mut source = LATIN.to_vec();
    let face = Font::new(&source, FontOptions::default()).unwrap();
    source.fill(0);
    let run = face.shape("office", 24.0).unwrap();
    assert!(run.width > 0.0 && run.glyphs.len() < 6);
    assert!(run.glyphs.iter().all(|g| g.glyph_id > 0));
    assert!(Font::new(b"invalid", FontOptions::default()).is_err());
    assert!(
        Font::new(
            LATIN,
            FontOptions {
                face_index: u32::MAX,
                ..FontOptions::default()
            }
        )
        .is_err()
    );
    assert!(
        Font::new(
            LATIN,
            FontOptions {
                weight: 0,
                ..FontOptions::default()
            }
        )
        .is_err()
    );
    assert!(face.shape("x", f32::NAN).is_err());
    assert!(face.shape(&"x".repeat(65_537), 16.0).is_err());
}

#[test]
fn hxn_glyphs_match_the_shared_multiscript_migration_fixtures() {
    for line in include_str!("../tests/fixtures/shaping-baseline.tsv").lines() {
        let row: Vec<_> = line.split('\t').collect();
        if row[2] != "default" {
            continue;
        }
        let bytes = match row[0] {
            "latin" => LATIN,
            "arabic" => ARABIC,
            "devanagari" => INDIC,
            _ => unreachable!(),
        };
        let face = Font::new(
            bytes,
            FontOptions {
                weight: row[1].parse().unwrap(),
                ..FontOptions::default()
            },
        )
        .unwrap();
        assert!(face.supports(row[3]));
        let run = face.shape(row[3], 16.0).unwrap();
        let scale = 16.0 / face.metrics(16.0).unwrap().units_per_em as f32;
        let expected: Vec<Vec<i32>> = row[4]
            .split(',')
            .map(|g| g.split(':').map(|v| v.parse().unwrap()).collect())
            .collect();
        assert_eq!(run.glyphs.len(), expected.len());
        for (g, e) in run.glyphs.iter().zip(expected) {
            assert_eq!(g.glyph_id, e[0] as u32);
            assert_eq!(g.cluster, e[5] as u32);
            assert!((g.x_advance - e[1] as f32 * scale).abs() < 0.0001);
            assert!((g.y_advance - e[2] as f32 * scale).abs() < 0.0001);
            assert!((g.x_offset - e[3] as f32 * scale).abs() < 0.0001);
            assert!((g.y_offset - e[4] as f32 * scale).abs() < 0.0001);
            assert!(row[3].is_char_boundary(g.cluster as usize));
        }
    }
}

fn apply(texture: &mut [u8], update: &AtlasUpdate) {
    let bpp = if update.kind == AtlasKind::Color {
        4
    } else {
        1
    };
    for row in 0..update.patch_height as usize {
        let dst = ((update.y as usize + row) * update.width as usize + update.x as usize) * bpp;
        let src = row * update.stride as usize;
        texture[dst..dst + update.stride as usize]
            .copy_from_slice(&update.pixels[src..src + update.stride as usize]);
    }
}
#[test]
fn atlas_updates_are_owned_and_each_consumer_can_catch_up() {
    let font = latin();
    let mut engine = TextEngine::new();
    let prepared = engine
        .prepare(&font, "Hello", TextOptions::default())
        .unwrap();
    assert!(!prepared.glyphs.is_empty());
    let first = engine.atlas(AtlasKind::Coverage, 0).unwrap();
    assert!(first.full && first.pixels.iter().any(|v| *v > 0));
    assert!(
        engine
            .atlas(AtlasKind::Coverage, first.revision)
            .unwrap()
            .pixels
            .is_empty()
    );
    let mut texture = first.pixels.clone();
    engine.prepare(&font, "W", TextOptions::default()).unwrap();
    let patch = engine.atlas(AtlasKind::Coverage, first.revision).unwrap();
    assert!(!patch.full && patch.revision > first.revision);
    apply(&mut texture, &patch);
    assert_eq!(
        texture,
        engine.atlas(AtlasKind::Coverage, 0).unwrap().pixels
    );
    let other = engine.atlas(AtlasKind::Coverage, first.revision).unwrap();
    assert_eq!(patch.pixels, other.pixels);
    let old_generation = engine.generation();
    engine.clear().unwrap();
    assert_ne!(old_generation, engine.generation());
    assert!(first.pixels.iter().any(|v| *v > 0));
    assert!(
        engine
            .atlas(AtlasKind::Coverage, patch.revision)
            .unwrap()
            .pixels
            .iter()
            .all(|v| *v == 0)
    );
}

#[test]
fn old_consumers_get_a_full_snapshot_and_fonts_can_be_released() {
    let font = latin();
    let retained = Arc::downgrade(&font.inner);
    let mut engine = TextEngine::new();
    engine.prepare(&font, "A", TextOptions::default()).unwrap();
    let revision = engine.atlas(AtlasKind::Coverage, 0).unwrap().revision;
    for index in 0..35 {
        engine
            .prepare(
                &font,
                "W",
                TextOptions {
                    size: 20.0 + index as f32,
                    ..TextOptions::default()
                },
            )
            .unwrap();
        engine.atlas(AtlasKind::Coverage, 0).unwrap();
    }
    assert!(engine.atlas(AtlasKind::Coverage, revision).unwrap().full);
    drop(font);
    assert!(retained.upgrade().is_some());
    engine.clear_fonts().unwrap();
    assert!(retained.upgrade().is_none());
}

#[test]
fn glyph_masks_survive_their_font_and_invalid_text_options_are_rejected() {
    let font = latin();
    let glyph = font.shape("A", 32.0).unwrap().glyphs[0].glyph_id;
    let bitmap = font.rasterize(glyph, 32.0, AtlasKind::Coverage).unwrap();
    assert_eq!(
        bitmap.pixels.len(),
        (bitmap.stride * bitmap.height) as usize
    );
    assert!(bitmap.pixels.iter().any(|v| *v > 0));
    assert!(font.rasterize(u32::MAX, 32.0, AtlasKind::Coverage).is_err());
    let mut engine = TextEngine::new();
    assert!(
        engine
            .prepare(
                &font,
                "hello",
                TextOptions {
                    scale: f32::INFINITY,
                    ..TextOptions::default()
                }
            )
            .is_err()
    );
    let wrapped = engine
        .prepare(
            &font,
            "hello world hello world",
            TextOptions {
                max_width: 60.0,
                ..TextOptions::default()
            },
        )
        .unwrap();
    assert!(wrapped.height > 16.0 * 1.2);
    drop(font);
    assert!(bitmap.pixels.iter().any(|v| *v > 0));
}

#[test]
fn woff2_owned_font_decoding_and_errors_are_explicit() {
    let face = Font::new(
        include_bytes!("../tests/fixtures/owned.woff2"),
        FontOptions::default(),
    )
    .unwrap();
    assert!(face.supports("M"));
    assert!(face.shape("M", 16.0).unwrap().width > 0.0);
    assert!(Font::new(b"wOF2invalid", FontOptions::default()).is_err());
}
