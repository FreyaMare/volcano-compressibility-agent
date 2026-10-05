"""Fixed (volcano-independent) text of the report: the general problem, the theoretical
framework and the method description. Condensed from Chapters 1, 3 and 4 of the thesis.
Placeholders {name} etc. are filled at render time."""

INTRO_GENERAL = """Ground deformation is one of the most direct and quantitative observables of volcanic unrest. InSAR and GNSS now resolve millimetre- to centimetre-scale displacements, and their physical interpretation rests on analytical sources embedded in an elastic half-space: the point-like spherical source of Mogi (1958), the dipping finite prolate spheroid of Yang et al. (1988) as corrected by Newman et al. (2006), and the horizontal penny-shaped crack of Fialko et al. (2001), as implemented in dMODELS (Battaglia et al., 2013).

It is common practice to equate the geodetically inverted cavity-volume change ΔV<sub>c</sub> with the volume of magma V<sub>e</sub> that entered the reservoir. Mass balance shows that the two are generally different: the pressure rise produced by an injection both compresses the resident magma and dilates the reservoir walls, so only part of the injected volume is expressed as cavity-volume change. For a linearly elastic system, V<sub>e</sub> = ΔV<sub>c</sub>(1 + β<sub>m</sub>/β<sub>c</sub>) = r<sub>V</sub>ΔV<sub>c</sub> (Rivalta and Segall, 2008), where β<sub>m</sub> is the magma compressibility and β<sub>c</sub> the chamber compressibility. The chamber term is purely mechanical and shape-dependent; the magma term is controlled above all by exsolved volatiles, because a vapour phase is two to three orders of magnitude more compressible than silicate melt (Kilbride et al., 2016; Segall, 2010).

For monitoring, this physics creates an ambiguity: the spatial wavelength of a deformation field constrains source depth within a specified source geometry and elastic model, but the amplitude is strongly non-unique. One centimetre of uplift may represent a small perturbation of a shallow, gas-rich level or a much larger batch of nearly incompressible magma at depth. Petrological and thermodynamic constraints do not make depth measurable where geodesy cannot; they translate a mechanically inferred cavity-volume change into physically plausible magma-transfer scenarios. This report carries that propagation, from published melt chemistry to predicted surface displacement, for {name}."""

APPROACH = """The method is a seven-step chain that translates a storage depth and a magma composition into a predicted surface displacement (Figure 3.1 of the La Fossa thesis; Freya Mohammadian, 2026):

1. From the storage depth z, the lithostatic pressure P = ρ<sub>c</sub>gz.
2. From P, temperature and bulk composition, the equilibrium state of the C–O–H–S volatiles — saturation pressure P<sub>sat</sub>, exsolved gas volume fraction φ and gas fugacities — computed with the thermodynamic code EVo (Liggins et al., 2020, 2022) using the solubility laws of Burgisser et al. (2015).
3. The magma compressibility, on two limiting branches: the frozen-phase mixture β<sub>m</sub> = φβ<sub>gas</sub> + (1 − φ)β<sub>liquid</sub> (rapid loading) and the equilibrium compressibility β<sub>m</sub><sup>eff</sup> = Δln ρ<sub>bulk</sub>/ΔP along the EVo path (slow loading).
4. The chamber compressibility β<sub>c</sub> from the reservoir shape: sphere, prolate spheroid or penny-shaped crack.
5. The volume-partitioning factor r<sub>V</sub> = 1 + β<sub>m</sub>/β<sub>c</sub>.
6. The reservoir volume change ΔV<sub>c</sub> = V<sub>e</sub>/r<sub>V</sub> for each injected volume.
7. The vertical surface displacement at the centre and at 1 and 2 km with the Mogi, Yang or Fialko source.

The inputs were assembled automatically from the published literature by a research agent; every input carries its source and a status code — measured (M), analytical upper limit (U), adopted representative value (A) or generic default (D) — and generic defaults are listed explicitly in Section 4.7. The chain is then inverted to give, for every configuration, the injected volume and overpressure required for {target} mm of central uplift."""

THEORY = [
    ("3.1 Pressure and depth",
     """Magma stored at depth z is assumed to be in lithostatic equilibrium with its overburden:""",
     "P = ρ<sub>c</sub> g z        (3.1)",
     """with ρ<sub>c</sub> the mean crustal density ({rho:g} kg m<sup>−3</sup> here). Equation (3.1) fixes the ambient state only; the overpressure ΔP that drives deformation is treated separately. For deep reservoirs the reference surface of z is immaterial, but for a shallow source the depth returned by a geodetic inversion is a coordinate below the model free surface, whereas the pressure depends on the real overburden. Because a gas-bearing magma near its saturation pressure has a gas fraction that varies steeply with P, the pressure datum of a shallow source is treated here as an explicit modelling assumption and varied (Section 5.6)."""),
    ("3.2 Volatile saturation, speciation and fugacity",
     """Each reservoir is characterised by its total budget of H<sub>2</sub>O, CO<sub>2</sub> and S. EVo solves the coupled C–O–H–S equilibria between melt and vapour — power-law solubilities calibrated for basaltic, phonolitic and rhyolitic melt classes (Burgisser et al., 2015), homogeneous gas equilibria among H<sub>2</sub>O, H<sub>2</sub>, CO<sub>2</sub>, CO, SO<sub>2</sub>, H<sub>2</sub>S and S<sub>2</sub>, oxygen fugacity buffered relative to FMQ (Frost, 1991) and coupled to the ferric–ferrous equilibrium (Kress and Carmichael, 1991). Run in saturation-finding mode, EVo locates P<sub>sat</sub> for the budget and decompresses at equilibrium to the reservoir pressure. If P<sub>sat</sub> < P the magma is undersaturated and φ = 0. The gas volume fraction follows from the gas mass fraction w<sub>g</sub> and the phase densities:""",
     "φ = (w<sub>g</sub>/ρ<sub>g</sub>) / [w<sub>g</sub>/ρ<sub>g</sub> + (1 − w<sub>g</sub>)/ρ<sub>l</sub>],      ρ<sub>g</sub> = P M̄ / (R T)        (3.2)",
     """with M̄ the mean molar mass of the equilibrium vapour."""),
    ("3.3 Magma compressibility",
     """For the vapour, the ideal-gas compressibility is β<sub>gas</sub> = 1/P; for the melt, β<sub>liquid</sub> = (0.5–2)×10<sup>−10</sup> Pa<sup>−1</sup> (Spera, 2000; Rivalta and Segall, 2008), adopted per composition. If a pressure increment is applied faster than volatiles can redistribute, the phase masses are frozen and""",
     "β<sub>m</sub> = φ β<sub>gas</sub> + (1 − φ) β<sub>liquid</sub>        (3.3)",
     """If loading is slow enough for dissolution equilibrium to be maintained, vapour redissolves as pressure rises and the effective compressibility, β<sub>m</sub><sup>eff</sup> = Δ ln ρ<sub>bulk</sub>/ΔP, evaluated along the EVo equilibrium path, is always the larger. The two are end-members selected by the ratio of the loading timescale to the diffusive timescale of gas–melt transfer (minutes for water in silicic melt at plausible bubble spacings), so that for unrest developing over weeks to months the equilibrium branch is the more likely. Both are reported wherever a reservoir is gas-bearing; where φ = 0 they coincide."""),
    ("3.4 Chamber compressibility",
     """The chamber compressibility β<sub>c</sub> = (1/V<sub>0</sub>) dV<sub>c</sub>/dP depends on shape and is proportional to 1/μ:""",
     "sphere: β<sub>c</sub> = 3/(4μ)<br/>prolate spheroid: β<sub>c</sub> = (3/4μ)[A²/3 − 0.7A + 1.37]<br/>penny crack: β<sub>c</sub> = 8(1 − ν)a³/(3μV<sub>0</sub>)        (3.4)",
     """The sphere value is exact (Segall, 2010). For the spheroid of aspect ratio A = b/a the bracket is the shape correction of the dMODELS prolate source (Battaglia et al., 2013), which reproduces the exact Eshelby compliance (Amoruso and Crescentini, 2009) to within about 1.5% across 0.05 ≤ A ≤ 1. For the penny-shaped crack the Fialko et al. (2001) half-space solution is used, which includes free-surface softening (about 29% at a/d = 1). The crack relation requires a thin crack: with mean opening w̄ = V<sub>0</sub>/(πa²), configurations with w̄/(2a) > 0.1 are stiff-walled idealisations rather than sills, and are flagged throughout."""),
    ("3.5 Volume partitioning",
     """An injected volume V<sub>e</sub> is accommodated by cavity dilation and by compression of the resident magma, V<sub>e</sub> = (β<sub>c</sub> + β<sub>m</sub>)V<sub>0</sub>ΔP, whence""",
     "ΔP = V<sub>e</sub> / [(β<sub>c</sub> + β<sub>m</sub>)V<sub>0</sub>],      r<sub>V</sub> = 1 + β<sub>m</sub>/β<sub>c</sub>,      ΔV<sub>c</sub> = V<sub>e</sub>/r<sub>V</sub>        (3.5)",
     """For a sphere this reduces to r<sub>V</sub> = 1 + 4μβ<sub>m</sub>/3 (Rivalta and Segall, 2008). Configurations requiring ΔP above {screen:g} MPa for the target signal are described as exceeding a reference screening threshold, a simplified proxy for host-rock strength used only to rank configurations."""),
    ("3.6 Elastic deformation sources",
     """The Mogi point source gives the vertical displacement at radial distance r""",
     "u<sub>z</sub>(r) = (1 − ν) ΔV<sub>c</sub> d / [π (d² + r²)<sup>3/2</sup>]        (3.6)",
     """The Yang et al. (1988) spheroid, with the corrections of Newman et al. (2006), and the Fialko et al. (2001) crack are evaluated numerically with dmodelspy, the Python port of dMODELS. All three are linear in source strength, so each source is evaluated once and scaled by ΔV<sub>c</sub>, and the chain can be inverted by proportionality. All are solutions for a homogeneous, isotropic elastic half-space with a flat surface: topography, layering and time-dependent rheology are not represented."""),
]

METHOD_REFS = [
    "Amoruso, A., Crescentini, L. (2009). Shape and volume change of pressurized ellipsoidal cavities from deformation and seismic data. J. Geophys. Res. 114, B02210.",
    "Battaglia, M., Cervelli, P.F., Murray, J.R. (2013). dMODELS: a MATLAB software package for modeling crustal deformation near active faults and volcanic centers. J. Volcanol. Geotherm. Res. 254, 1–4.",
    "Burgisser, A., Alletti, M., Scaillet, B. (2015). Simulating the behavior of volatiles belonging to the C–O–H–S system in silicate melts under magmatic conditions with the software D-Compress. Comput. Geosci. 79, 1–14.",
    "Fialko, Y., Khazan, Y., Simons, M. (2001). Deformation due to a pressurized horizontal circular crack in an elastic half-space, with applications to volcano geodesy. Geophys. J. Int. 146, 181–190.",
    "Frost, B.R. (1991). Introduction to oxygen fugacity and its petrologic importance. Rev. Mineral. 25, 1–9.",
    "Heap, M.J., Villeneuve, M., Albino, F., et al. (2020). Towards more realistic values of elastic moduli for volcano modelling. J. Volcanol. Geotherm. Res. 390, 106684.",
    "Kilbride, B.M., Edmonds, M., Biggs, J. (2016). Observing eruptions of gas-rich compressible magmas from space. Nat. Commun. 7, 13744.",
    "Kress, V.C., Carmichael, I.S.E. (1991). The compressibility of silicate liquids containing Fe2O3 and the effect of composition, temperature, oxygen fugacity and pressure on their redox states. Contrib. Mineral. Petrol. 108, 82–92.",
    "Le Maitre, R.W. (1976). The chemical variability of some common igneous rocks. J. Petrol. 17, 589–637.",
    "Liggins, P., Shorttle, O., Rimmer, P.B. (2020). Can volcanism build hydrogen-rich early atmospheres? Earth Planet. Sci. Lett. 550, 116546.",
    "Liggins, P., Jordan, S., Rimmer, P.B., Shorttle, O. (2022). Growth and evolution of secondary volcanic atmospheres: I. Identifying the geological character of hot rocky planets. J. Geophys. Res. Planets 127, e2021JE007123.",
    "Mogi, K. (1958). Relations between the eruptions of various volcanoes and the deformations of the ground surfaces around them. Bull. Earthq. Res. Inst. Univ. Tokyo 36, 99–134.",
    "Mohammadian, Freya (2026). From magma compressibility to surface deformation at La Fossa volcano (Vulcano Island, Italy). MSc thesis, University of Naples Federico II. Code: github.com/FreyaMare/lafossa-magma-compressibility.",
    "Mohammadian, Freya (2026). Volcano Compressibility Agent (version 1.0.0) [software]. github.com/FreyaMare/volcano-compressibility-agent.",
    "Newman, A.V., Dixon, T.H., Gourmelen, N. (2006). A four-dimensional viscoelastic deformation model for Long Valley Caldera, California, between 1995 and 2000. J. Volcanol. Geotherm. Res. 150, 244–269.",
    "Rivalta, E., Segall, P. (2008). Magma compressibility and the missing source for some dike intrusions. Geophys. Res. Lett. 35, L04306.",
    "Segall, P. (2010). Earthquake and Volcano Deformation. Princeton University Press.",
    "Spera, F.J. (2000). Physical properties of magma. In: Sigurdsson, H. (Ed.), Encyclopedia of Volcanoes. Academic Press, 171–190.",
    "Yang, X.-M., Davis, P.M., Dieterich, J.H. (1988). Deformation from inflation of a dipping finite prolate spheroid in an elastic half-space as a model for volcanic stressing. J. Geophys. Res. 93(B5), 4249–4257.",
]
