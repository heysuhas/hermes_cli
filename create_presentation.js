const pptxgen = require("pptxgenjs");

// Configuration based on 'pptx' skill design principles:
// - Theme: Midnight Executive (Primary: #1E2761, Secondary: #CADCFC, Accent: #FFFFFF)
// - Layout: 16:9
// - Font Pair: Arial Black (Header), Calibri (Body)

let pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.author = 'Hermes Assistant';
pres.title = 'Welcome to the Platform';

let slide = pres.addSlide();

// Background color for the whole slide (Midnight Executive: #1E2761)
slide.background = { color: "1E2761" };

// Add a large title with high contrast
slide.addText("Welcome to the Platform", {
    x: 0.5,
    y: 1.5,
    w: 9,
    h: 2,
    fontSize: 44,
    fontFace: "Arial Black",
    color: "FFFFFF", // White accent/contrast
    bold: true,
    align: "left"
});

// Add a sub-header or descriptive text with more contrast (Secondary Color)
slide.addText("A glimpse into the future of automation.", {
    x: 0.5,
    y: 3.5,
    w: 9,
    h: 1,
    fontSize: 24,
    fontFace: "Calibri",
    color: "CADCFC", // Ice blue secondary color
    bold: true
});

// Add a primary visual element (a content block)
slide.addShape(pres.ShapeType.RECTANGLE, {
    x: 0.5,
    y: 4.8,
    w: 4,
    h: 1.5,
    fill: { color: "CADCFC" },
    line: { width: 2, color: "FFFFFF" }
});

slide.addText("Key Feature 01", {
    x: 0.7,
    y: 5.3,
    w: 3.6,
    h: 1,
    fontSize: 20,
    fontFace: "Arial Black",
    color: "1E2761", // Contrast against the light background
});

// Save the file
pres.writeFile({ fileName: "sample_deck.pptx" });
