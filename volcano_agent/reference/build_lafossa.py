"""Builds lafossa.json: the La Fossa (Vulcano) dataset of the MSc thesis, Scenario A,
transcribed from Tables 2.1, 2.2, 4.1, 4.2 and 4.3 of the thesis.

It serves three purposes: (1) regression test of the generalised engine against the
thesis numbers; (2) a worked example of the expected depth of provenance, shown to the
research agent; (3) an offline demo of the report generator.

Run:  python -m volcano_agent.reference.build_lafossa
"""
import os

from volcano_agent.schema import Dataset, DeformationSource, Level, Magma, Q, Reference

G98, C94, F15, P13, DT23, H20 = ("Gioncada et al. (1998)", "Clocchiatti et al. (1994)",
                                 "Fusillo et al. (2015)", "Paonita et al. (2013)",
                                 "Di Traglia et al. (2023)", "Heap et al. (2020)")

ds = Dataset(
    name="La Fossa (Vulcano Island)",
    country="Italy", region="Aeolian Islands, southern Tyrrhenian Sea",
    latitude=38.404, longitude=14.962,
    volcano_type="Composite cone (tuff cone) within the La Fossa Caldera",
    tectonic_setting="Volcanic arc related to subduction and roll-back of the Ionian slab; Tindari-Letojanni strike-slip fault system",
    last_eruption="1888-1890 (Vulcanian eruption)",
    summit_elevation_m=Q(value=391, status="M", source="De Astis et al. (1997)", note="height of the La Fossa cone"),
    caldera_max_radius_km=Q(value=2.0, status="A", source="Di Traglia et al. (2024)",
                            note="La Fossa Caldera ~4 x 2 km; half of the long axis bounds sill radius"),
    rho_crust=Q(value=2500, status="A", note="mean density of edifice and basement; range 2300-2700"),
    mu_deep_GPa=Q(value=10, status="A", source=H20, note="intact-rock end of 1-10 GPa"),
    nu_deep=Q(value=0.25, status="A"),
    mu_shallow_GPa=Q(value=1, status="A", source=f"{H20}; {DT23}", note="damaged, hydrothermally altered rock"),
    nu_shallow=Q(value=0.35, status="A", source=DT23),
    dFMQ=Q(value=1.0, status="A", note="oxidised arc magmas"),
    magmas=[
        Magma(key="RHYOLITE", rock_type="rhyolite", label="GS91-50c, 1888-1890 eruption",
              oxides=dict(SIO2=73.54, TIO2=0.13, AL2O3=13.10, FEO=2.21, MNO=0.07, MGO=0.34, CAO=1.02,
                          NA2O=4.35, K2O=4.95, P2O5=0.04),
              composition_status="M", composition_source=f"{G98}, Table 1",
              T_C=Q(value=1000, min=1000, max=1030, status="M", source=C94),
              H2O_wt=Q(value=1.25, min=1.0, max=1.5, status="A", source=C94,
                       note="midpoint of 1-1.5 wt% reported for the 1888-1890 magmas; no rhyolite-specific MI data"),
              CO2_wt=Q(value=0.005, status="U", source=F15, note="highest Vulcano detection limit (~50 ppm) assigned"),
              S_wt=Q(value=0.02, status="U", source=G98, note="below detection in rhyolitic groundmass; assigned"),
              beta_liquid=Q(value=1.2e-10, status="A", source="Spera (2000); Rivalta and Segall (2008)")),
        Magma(key="TRACHYTE", rock_type="trachyte", label="Palizzi pumices, TR column",
              oxides=dict(SIO2=61.60, TIO2=0.61, AL2O3=17.51, FEO=4.30, MNO=0.10, MGO=1.25, CAO=2.25,
                          NA2O=4.42, K2O=7.25, P2O5=0.22),
              composition_status="M", composition_source=f"{G98}, Table 1",
              T_C=Q(value=1075, min=1050, max=1100, status="A", source=C94),
              H2O_wt=Q(value=1.25, min=1.0, max=1.5, status="A", source=C94, note="~1 wt% measured in 1888-1890 trachyte MIs"),
              CO2_wt=Q(value=0.005, status="U", source=F15),
              S_wt=Q(value=0.07, status="M", source=G98),
              beta_liquid=Q(value=1.1e-10, status="A", source="Spera (2000); Rivalta and Segall (2008)")),
        Magma(key="LATITE", rock_type="latite", label="GS91-17, Pietre Cotte",
              oxides=dict(SIO2=57.45, TIO2=0.61, AL2O3=16.83, FEO=6.60, MNO=0.14, MGO=2.58, CAO=5.17,
                          NA2O=3.81, K2O=5.67, P2O5=0.43),
              composition_status="M", composition_source=f"{G98}, Table 1",
              T_C=Q(value=1080, min=1070, max=1090, status="M", source=f"{G98}; {P13}"),
              H2O_wt=Q(value=1.35, min=0.8, max=1.9, status="A", source=G98, note="midpoint of measured 0.8-1.9 wt%"),
              CO2_wt=Q(value=0.005, status="U", source=G98, note="below detection"),
              S_wt=Q(value=0.10, status="M", source=G98),
              beta_liquid=Q(value=1.0e-10, status="A", source="Spera (2000); Rivalta and Segall (2008)")),
        Magma(key="SHOSHONITE", rock_type="shoshonite", label="GS91-66, Vulcanello I",
              oxides=dict(SIO2=53.79, TIO2=0.70, AL2O3=15.08, FEO=8.16, MNO=0.16, MGO=4.70, CAO=7.67,
                          NA2O=3.55, K2O=4.89, P2O5=0.39),
              composition_status="M", composition_source=f"{G98}, Table 1",
              T_C=Q(value=1100, status="M", source=F15),
              H2O_wt=Q(value=0.85, min=0.36, max=1.32, status="A", source=F15),
              CO2_wt=Q(value=0.022, status="A", source=P13, note="220 ppm degassing-model estimate at 100 MPa"),
              S_wt=Q(value=0.03, min=0.01, max=0.05, status="A", source=F15),
              beta_liquid=Q(value=0.8e-10, status="A", source="Spera (2000); Rivalta and Segall (2008)")),
    ],
    levels=[
        Level(name="Shallow La Fossa reservoir", depth_km=Q(value=2.0, min=1.5, max=2.0, status="A", source=C94),
              pressure_MPa=Q(value=45, min=30, max=60, status="M", source=C94), resident="RHYOLITE",
              injected="TRACHYTE", V0_m3=Q(value=5e8, status="A", note="reference scheme"),
              evidence="Fluid-inclusion barometry on 1888-1890 xenoliths (30-60 MPa); degassing models adopt ~38 MPa"),
        Level(name="Intermediate reservoir", depth_km=Q(value=5.0, min=3.0, max=5.0, status="A", source="Peccerillo et al. (2006)"),
              pressure_MPa=Q(value=100, status="A", source="Peccerillo et al. (2006)"), resident="TRACHYTE",
              injected="LATITE", V0_m3=Q(value=5e9, status="A", note="reference scheme"),
              evidence="Upper-crustal density barrier; Vulcanello storage at 3-5 km; latite feeding fumaroles at 3-4 km"),
        Level(name="Deep reservoir", depth_km=Q(value=12.0, status="A", source="Zanon et al. (2003)"),
              pressure_MPa=Q(value=300, status="A", source="Zanon et al. (2003)"), resident="LATITE",
              injected="SHOSHONITE", V0_m3=Q(value=5e10, status="A", note="reference scheme"),
              evidence="Felsic granulite-metapelite boundary; CO2-rich fluid inclusions in xenoliths"),
    ],
    deformation_source=DeformationSource(
        model="YANG", depth_km=Q(value=0.598, min=0.548, max=0.648, status="M", source=f"{DT23}, Table S1"),
        depth_reference="below sea level",
        a_m=Q(value=595, status="M", source=DT23), b_m=Q(value=59, status="M", source=DT23),
        aspect=Q(value=0.099, status="M", source=DT23),
        dip_deg=Q(value=69, status="M", source=DT23), strike_deg=Q(value=137, status="M", source=DT23),
        V0_m3=Q(value=8.83e6, status="M", source=DT23), dV_m3=Q(value=73108, status="M", source=f"{DT23}, Table S1"),
        dP_MPa=Q(value=8.48, status="M", source=DT23), mu_GPa=Q(value=1, status="A", source=DT23),
        nu=Q(value=0.35, status="A", source=DT23), resident="RHYOLITE", injected="TRACHYTE",
        period="15 July - 18 December 2021", interpretation="Expansion of the shallow hydrothermal system fed by magmatic fluids from 3-5 km",
        source=DT23),
    narrative={
        "setting": "Vulcano is the southernmost island of the Aeolian arc (De Astis et al., 1997).",
        "unrest": "Since September 2021 Vulcano has experienced its strongest unrest in decades (Aiuppa et al., 2022; Di Traglia et al., 2023).",
    },
    references=[
        Reference(key=G98, citation="Gioncada, A., Clocchiatti, R., Sbrana, A., Bottazzi, P., Massare, D., Ottolini, L. (1998). A study of melt inclusions at Vulcano (Aeolian Islands, Italy): insights on the primitive magmas and on the volcanic feeding system. Bull. Volcanol. 60, 286-306."),
        Reference(key=C94, citation="Clocchiatti, R., Del Moro, A., Gioncada, A., Joron, J.L., Mosbah, M., Pinarelli, L., Sbrana, A. (1994). Assessment of a shallow magmatic system: the 1888-90 eruption, Vulcano Island, Italy. Bull. Volcanol. 56, 466-486."),
        Reference(key=F15, citation="Fusillo, R., Di Traglia, F., Gioncada, A., Pistolesi, M., Wallace, P.J., Rosi, M. (2015). Deciphering post-caldera volcanism: insight into the Vulcanello (Island of Vulcano, Southern Italy) eruptive activity. Bull. Volcanol. 77, 76."),
        Reference(key=P13, citation="Paonita, A., Federico, C., Bonfanti, P., et al. (2013). The episodic and abrupt geochemical changes at La Fossa fumaroles (Vulcano Island, Italy) and related constraints on the dynamics, structure, and compositions of the magmatic system. Geochim. Cosmochim. Acta 120, 158-178."),
        Reference(key=DT23, citation="Di Traglia, F., et al. (2023). Multi-temporal InSAR, GNSS and seismic measurements reveal the origin of the 2021 Vulcano Island (Italy) unrest. Geophys. Res. Lett. 50, e2023GL104952.", doi="10.1029/2023GL104952"),
        Reference(key=H20, citation="Heap, M.J., et al. (2020). Towards more realistic values of elastic moduli for volcano modelling. J. Volcanol. Geotherm. Res. 390, 106684."),
    ],
)

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "lafossa.json")
    with open(out, "w") as f:
        f.write(ds.model_dump_json(indent=1))
    print("wrote", out)
