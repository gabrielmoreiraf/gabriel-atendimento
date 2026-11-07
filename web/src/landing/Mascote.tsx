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
          <stop offset="0" stopColor="#1d4683" />
          <stop offset="0.55" stopColor="#2659a5" />
          <stop offset="1" stopColor="#3dbfef" />
        </linearGradient>
        <linearGradient id="fio-rosto" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0b1a33" />
          <stop offset="1" stopColor="#10284d" />
        </linearGradient>
      </defs>
      <path
        d="M70 40h180a40 40 0 0 1 40 40v120a40 40 0 0 1-40 40H150l-56 44a8 8 0 0 1-13-6l3-38H70a40 40 0 0 1-40-40V80a40 40 0 0 1 40-40Z"
        fill="url(#fio-corpo)"
      />
      <rect x="62" y="74" width="196" height="132" rx="34" fill="url(#fio-rosto)" />
      <g className={piscando ? "mascote__olhos" : undefined} fill="#d7d900">
        <ellipse cx="124" cy="138" rx="17" ry="21" />
        <ellipse cx="196" cy="138" rx="17" ry="21" />
      </g>
      <path
        d="M140 176q20 14 40 0"
        stroke="#d7d900"
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

/** Marca compacta do FIO (só o rosto do mascote), para ícones pequenos como a bolha da navegação. */
export function MascoteMarca({ tamanho = 28 }: { tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 64 64" role="img" aria-label="FIO">
      <rect x="2" y="6" width="60" height="46" rx="14" fill="#2659a5" />
      <path d="M18 50 12 62l16-10Z" fill="#2659a5" />
      <rect x="9" y="13" width="46" height="32" rx="10" fill="#0b1a33" />
      <ellipse cx="24" cy="27" rx="5" ry="6" fill="#d7d900" />
      <ellipse cx="40" cy="27" rx="5" ry="6" fill="#d7d900" />
      <path
        d="M26 37q6 4 12 0"
        stroke="#d7d900"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
