/** Mascote do FIO: um balão de conversa com olhos e um fio que sai da cauda (o fio do pedido). */
export function Mascote({
  tamanho = 320,
  piscando = true,
}: { tamanho?: number; piscando?: boolean }) {
  return (
    <svg
      className="mascote"
      width={tamanho}
      height={tamanho}
      viewBox="0 0 320 320"
      role="img"
      aria-label="Mascote do FIO: um balão de conversa sorridente"
    >
      <defs>
        <linearGradient id="fio-corpo" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#6d3be0" />
          <stop offset="0.55" stopColor="#c44ad8" />
          <stop offset="1" stopColor="#f7a98a" />
        </linearGradient>
        <linearGradient id="fio-rosto" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1b1029" />
          <stop offset="1" stopColor="#2b1840" />
        </linearGradient>
      </defs>
      <path
        d="M70 40h180a40 40 0 0 1 40 40v120a40 40 0 0 1-40 40H150l-56 44a8 8 0 0 1-13-6l3-38H70a40 40 0 0 1-40-40V80a40 40 0 0 1 40-40Z"
        fill="url(#fio-corpo)"
      />
      <rect x="62" y="74" width="196" height="132" rx="34" fill="url(#fio-rosto)" />
      <g className={piscando ? "mascote__olhos" : undefined} fill="#ffffff">
        <ellipse cx="124" cy="138" rx="17" ry="21" />
        <ellipse cx="196" cy="138" rx="17" ry="21" />
      </g>
      <path
        d="M140 176q20 14 40 0"
        stroke="#f7a98a"
        strokeWidth="7"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M86 316c18-6 30-20 52-24 30-6 46 14 78 8"
        stroke="url(#fio-corpo)"
        strokeWidth="6"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
