"""Motor de políticas (W2): puro, sem I/O."""

from atendimento.politicas.motor import decidir, dentro_da_janela, supervisor_no_turno

__all__ = ["decidir", "dentro_da_janela", "supervisor_no_turno"]
