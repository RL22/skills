// Style tokens distilled from the Carrd "extras: notes" sketches (see references/notation.md).
// Change the look here, not in components.
window.CSI = window.CSI || {};
CSI.tokens = {
  paper: {
    plain: { bg: '#FFFDE7', grid: null },
    grid: { bg: '#F8F4DC', grid: '#8C9AA8', cell: 22 },
    white: { bg: '#FBFAF6', grid: null },
  },
  ink: {
    primary: '#1E1E1E', // felt-tip black — all structure
    note: '#8A8A8A',    // grey pen — margin notes, leader lines
    red: '#D83A2E',     // semantic accent only
    green: '#2E9A5A',   // semantic accent only
    blue: '#2F5DA8',
  },
  font: {
    hand: '"Architects Daughter", "Comic Sans MS", cursive', // labels, UI copy
    note: '"Caveat", cursive',                                // margin notes
    alt: '"Nanum Pen Script", cursive',
  },
  stroke: { frame: 1.9, detail: 1.35, fine: 1.0 },
  rough: { roughness: 1.1, bowing: 1.3 },
  hachure: { gap: 4.2, angle: -41, weight: 1.1 },
  size: { text: 16, small: 13, heading: 22, note: 21 },
};
