// The dataset has no photographs, so each product gets an illustration drawn
// from its real category and colour. It is labelled as an illustration.
const COLORS = {
  Beige: "#d9c3a0",
  Black: "#22252b",
  Blue: "#3b6fd4",
  Grey: "#8b909a",
  Maroon: "#7d1f36",
  Mustard: "#d9a21b",
  Navy: "#1f2f5c",
  Olive: "#6b7135",
  Pink: "#e57aa3",
  Red: "#d2323b",
  Teal: "#1f8a8a",
  White: "#f5f5f2",
};

const TEE = "M62 38 L88 28 Q100 46 112 28 L138 38 L176 76 L154 98 L140 84 L140 206 L60 206 L60 84 L46 98 L24 76 Z";
const LONG = "M62 38 L88 28 Q100 46 112 28 L138 38 L182 150 L160 158 L140 90 L140 206 L60 206 L60 90 L40 158 L18 150 Z";
const SHAPES = {
  "T-Shirts": { d: TEE },
  Tops: { d: "M66 42 L88 30 Q100 48 112 30 L134 42 L166 78 L148 96 L138 86 L138 178 L62 178 L62 86 L52 96 L34 78 Z" },
  Shirts: { d: LONG, extra: "collar" },
  Hoodies: { d: LONG, extra: "hood" },
  Jackets: { d: LONG, extra: "zip" },
  Jeans: { d: "M64 30 H136 L148 212 H108 L100 96 L92 212 H52 Z", extra: "seam" },
  Trousers: { d: "M66 30 H134 L142 212 H106 L100 96 L94 212 H58 Z", extra: "seam" },
  Dresses: { d: "M86 30 H114 L120 78 L156 212 H44 L80 78 Z", extra: "waist" },
  Kurtas: { d: "M62 34 L88 26 Q100 42 112 26 L138 34 L170 74 L150 88 L140 76 L146 218 H54 L60 76 L50 88 L30 74 Z", extra: "placket" },
  Innerwear: { d: "M56 80 H144 L134 130 Q100 168 66 130 Z" },
  Sneakers: { shoe: true },
  "Casual Shoes": { shoe: true },
};

function Extras({ kind, ink }) {
  const line = { stroke: ink, strokeWidth: 2, fill: "none", opacity: 0.45, strokeLinecap: "round" };
  switch (kind) {
    case "collar":
      return (
        <>
          <path d="M88 28 L100 56 L112 28" {...line} />
          <path d="M100 56 V206" {...line} strokeDasharray="1 9" />
        </>
      );
    case "hood":
      return <path d="M76 34 Q100 4 124 34 Q100 60 76 34" {...line} />;
    case "zip":
      return <path d="M100 40 V206" {...line} />;
    case "seam":
      return <path d="M64 44 H136 M100 96 V60" {...line} />;
    case "waist":
      return <path d="M79 92 Q100 100 121 92" {...line} />;
    case "placket":
      return <path d="M100 40 V120" {...line} />;
    default:
      return null;
  }
}

export default function ProductImage({ product, className = "", large = false }) {
  const fill = COLORS[product.color] ?? "#9aa0ad";
  const light = ["White", "Beige"].includes(product.color);
  const ink = light ? "#3b3f4a" : "#ffffff";
  const shape = SHAPES[product.category] ?? SHAPES["T-Shirts"];
  const bg = light ? "#f1eee9" : `${fill}22`;

  return (
    <svg className={`product-image ${className}`} viewBox="0 0 200 240" role="img" aria-label={`${product.name} (illustration)`} preserveAspectRatio="xMidYMid meet">
      <rect width="200" height="240" fill={bg} />
      <ellipse cx="100" cy="222" rx="62" ry="6" fill="#000" opacity="0.08" />
      {shape.shoe ? (
        <g stroke={light ? "#8f8a80" : "none"} strokeWidth="1.5">
          <path d="M28 150 Q28 118 62 116 L92 134 L122 126 Q176 130 178 162 L178 178 H28 Z" fill={fill} />
          <path d="M28 178 H178 V190 Q178 194 172 194 H34 Q28 194 28 190 Z" fill={light ? "#d8d4cb" : "#f5f5f2"} />
          <path d="M70 140 l8 -8 M84 146 l8 -8 M98 148 l8 -8" stroke={ink} strokeWidth="2" opacity="0.6" strokeLinecap="round" />
        </g>
      ) : (
        <g stroke={light ? "#8f8a80" : "none"} strokeWidth="1.5" strokeLinejoin="round">
          <path d={shape.d} fill={fill} />
          <Extras kind={shape.extra} ink={ink} />
        </g>
      )}
      {large && (
        <text x="100" y="236" textAnchor="middle" fontSize="7" fill="#9aa0ad" fontFamily="sans-serif">
          Illustration
        </text>
      )}
    </svg>
  );
}
