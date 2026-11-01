// Single source for the layer colours: the graph canvas and tailwind.config.js both read this.
export const LAYER_COLORS = {
  public: '#059669',
  internal: '#2563eb',
  confidential: '#d97706',
};
export const LAYERS = Object.keys(LAYER_COLORS);
