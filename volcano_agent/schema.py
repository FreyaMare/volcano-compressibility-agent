"""Data model of a volcano dataset, with provenance on every number.

Every physical input carries a *status* code, the same classification used in the
La Fossa thesis (Table 4.2), extended with one code for values the agent could not
find in the literature:

    M  measured value          an analysed / observed quantity for this volcano
    U  analytical upper limit  a below-detection result assigned as a positive number
    A  adopted value           a representative figure chosen within a published range,
                               or transferred from a related composition
    D  generic default         NOT volcano-specific: a textbook value used because no
                               published constraint was found (always flagged in the report)
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["M", "U", "A", "D"]

STATUS_LABEL = {
    "M": "measured",
    "U": "analytical upper limit",
    "A": "adopted representative value",
    "D": "generic default (not volcano-specific)",
}


class Q(BaseModel):
    """A sourced quantity."""
    value: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    status: Status = "D"
    source: str = ""
    note: str = ""

    def v(self, default: Optional[float] = None) -> Optional[float]:
        return self.value if self.value is not None else default

    @property
    def known(self) -> bool:
        return self.value is not None


OXIDES = ["SIO2", "TIO2", "AL2O3", "FEO", "MNO", "MGO", "CAO", "NA2O", "K2O", "P2O5"]


class Magma(BaseModel):
    key: str                                   # upper-case identifier, e.g. "RHYOLITE"
    rock_type: str = ""                        # basalt, andesite, latite, trachyte, rhyolite ...
    label: str = ""                            # sample / unit / eruption
    oxides: Dict[str, float] = Field(default_factory=dict)   # wt%, FeO = total iron
    composition_status: Status = "D"
    composition_source: str = ""
    T_C: Q = Field(default_factory=Q)
    H2O_wt: Q = Field(default_factory=Q)
    CO2_wt: Q = Field(default_factory=Q)
    S_wt: Q = Field(default_factory=Q)
    beta_liquid: Q = Field(default_factory=Q)
    evo_class: str = ""                        # set by finalize(): basalt / phonolite / rhyolite
    rho_melt: float = 2400.0


class Level(BaseModel):
    """A magmatic storage level of the plumbing system."""
    name: str
    depth_km: Q = Field(default_factory=Q)     # depth used for P = rho g z and for the source
    pressure_MPa: Q = Field(default_factory=Q) # published pressure estimate (for comparison only)
    resident: str = ""                         # Magma.key controlling beta_m
    injected: str = ""                         # Magma.key of the recharge (label only)
    V0_m3: Q = Field(default_factory=Q)
    evidence: str = ""


class DeformationSource(BaseModel):
    """A published geodetic source model of a recent unrest episode."""
    model: Literal["MOGI", "YANG", "PENNY"] = "MOGI"
    depth_km: Q = Field(default_factory=Q)     # centroid depth below the model free surface
    depth_reference: str = "below sea level"
    a_m: Q = Field(default_factory=Q)          # YANG semi-major axis; MOGI / PENNY radius
    b_m: Q = Field(default_factory=Q)          # YANG semi-minor axis
    aspect: Q = Field(default_factory=Q)       # YANG b/a if published directly (else b/a)
    dip_deg: Q = Field(default_factory=Q)      # YANG plunge from horizontal
    strike_deg: Q = Field(default_factory=Q)   # YANG down-dip azimuth, clockwise from N
    V0_m3: Q = Field(default_factory=Q)
    dV_m3: Q = Field(default_factory=Q)        # published cavity volume change
    dP_MPa: Q = Field(default_factory=Q)       # published overpressure
    mu_GPa: Q = Field(default_factory=Q)
    nu: Q = Field(default_factory=Q)
    resident: str = ""
    injected: str = ""
    period: str = ""
    interpretation: str = ""
    source: str = ""
    observed_uplift_mm: Q = Field(default_factory=Q)


class Reference(BaseModel):
    key: str                                   # "Gioncada et al. (1998)"
    citation: str = ""                         # full reference
    url: str = ""
    doi: str = ""


class Dataset(BaseModel):
    name: str
    country: str = ""
    region: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    volcano_type: str = ""
    tectonic_setting: str = ""
    last_eruption: str = ""
    summit_elevation_m: Q = Field(default_factory=Q)
    caldera_max_radius_km: Q = Field(default_factory=Q)
    rho_crust: Q = Field(default_factory=Q)
    mu_deep_GPa: Q = Field(default_factory=Q)
    nu_deep: Q = Field(default_factory=Q)
    mu_shallow_GPa: Q = Field(default_factory=Q)
    nu_shallow: Q = Field(default_factory=Q)
    dFMQ: Q = Field(default_factory=Q)
    magmas: List[Magma] = Field(default_factory=list)
    levels: List[Level] = Field(default_factory=list)
    deformation_source: Optional[DeformationSource] = None
    # narrative notes gathered by the research agent (with in-text citations)
    narrative: Dict[str, str] = Field(default_factory=dict)
    references: List[Reference] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)
    research_log: List[str] = Field(default_factory=list)

    def magma(self, key: str) -> Magma:
        for m in self.magmas:
            if m.key == key:
                return m
        raise KeyError(key)

    @property
    def slug(self) -> str:
        import re
        return re.sub(r"[^A-Za-z0-9]+", "_", self.name).strip("_") or "volcano"
