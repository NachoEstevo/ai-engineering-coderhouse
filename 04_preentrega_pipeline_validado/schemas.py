from enum import Enum

from pydantic import BaseModel, Field


class NivelCriticidad(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


class ExtraccionTecnica(BaseModel):
    tecnologias: list[str] = Field(
        min_length=1,
        description="Tecnologías, servicios o componentes técnicos mencionados en el texto.",
    )
    nivel_de_criticidad: NivelCriticidad = Field(
        description="Impacto técnico estimado: baja, media o alta.",
    )
    resumen_tecnico: str = Field(
        min_length=10,
        description="Resumen técnico breve del incidente o arquitectura descrita.",
    )
