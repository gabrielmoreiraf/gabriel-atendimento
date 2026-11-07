import { rotuloEstado } from "../formato";

export function EstadoSelo({ estado }: { estado: string }) {
  return (
    <span className="selo" data-estado={estado}>
      {rotuloEstado(estado)}
    </span>
  );
}
