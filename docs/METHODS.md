# Methods: the seven-step chain

The physics is that of Chapter 3 of the MSc thesis *From magma compressibility to surface deformation at
La Fossa volcano (Vulcano Island, Italy)*; the implementation in `volcano_agent/physics.py` and
`volcano_agent/chain.py` is the thesis notebook generalised to any volcano.

## 1. Lithostatic pressure
$$P = \rho_c\, g\, z \qquad (3.1)$$
For a shallow published source, *z* is the model depth by default (sea-level datum); the datum is varied
in the sensitivity analysis because the real overburden can differ substantially.

## 2. Volatile equilibrium (EVo)
EVo (Liggins et al. 2020, 2022), pinned to commit `2487939`, solves the closed-system C–O–H–S equilibrium
between melt and vapour: solubilities of Burgisser et al. (2015) for the basalt / phonolite / rhyolite class
of the melt, homogeneous gas equilibria, fugacities $f_i=\gamma_i x_i P$, $f_{O_2}$ buffered at FMQ + ΔFMQ
(Frost 1991) and coupled to the ferric–ferrous equilibrium (Kress & Carmichael 1991). In saturation-finding
mode EVo finds $P_{sat}$ and decompresses to the reservoir pressure; if $P_{sat} < P$, φ = 0.
$$\varphi = \frac{w_g/\rho_g}{w_g/\rho_g + (1-w_g)/\rho_l}, \qquad \rho_g = \frac{P\bar M}{RT} \qquad (3.2)$$
If EVo cannot be installed or does not converge for a state, an analytic fallback (square-root H₂O and Henrian CO₂
solubility) is used for that state and the report says so. When the melt temperature lies outside the calibrated
range of EVo's temperature-dependent H₂O solubility law, EVo continues with temperature-independent coefficients
(its intended behaviour; the warning routine of the pinned commit contains an invalid format string and is
replaced here by one that records the event), and the report flags the state.

## 3. Magma compressibility
$$\beta_{gas} = 1/P, \qquad \beta_m = \varphi\,\beta_{gas} + (1-\varphi)\,\beta_{liquid} \quad\text{(frozen, rapid loading)} \qquad (3.3)$$
$$\beta_m^{eff} = \Delta \ln \rho_{bulk} / \Delta P \quad\text{(equilibrium, slow loading, along the EVo path)}$$

## 4. Chamber compressibility
$$\beta_c = \frac{3}{4\mu}\ \text{(sphere)}, \qquad
\beta_c = \frac{3}{4\mu}\left[\frac{A^2}{3} - 0.7A + 1.37\right]\ \text{(prolate spheroid, } A=b/a),$$
$$\beta_c = \frac{\Delta V_{Fialko}}{V_0\,\Delta P}\ \text{(penny crack, half-space; full-space limit } 8(1-\nu)a^3/(3\mu V_0)) \qquad (3.4)$$
Thin-crack condition: $\bar w/(2a) \le 0.1$ with $\bar w = V_0/(\pi a^2)$.

## 5–6. Volume partitioning
$$\Delta P = \frac{V_e}{(\beta_c+\beta_m)V_0}, \qquad r_V = 1 + \frac{\beta_m}{\beta_c}, \qquad \Delta V_c = \frac{V_e}{r_V} \qquad (3.5)$$

## 7. Surface displacement
$$u_z(r) = \frac{(1-\nu)\,\Delta V_c\, d}{\pi\,(d^2 + r^2)^{3/2}} \quad\text{(Mogi)} \qquad (3.6)$$
Yang et al. (1988) spheroid with Newman et al. (2006) corrections and the Fialko et al. (2001) crack via
`dmodelspy` (with the two NumPy-2 corrections of the thesis). All sources are linear: each is evaluated once
and scaled by ΔV_c, so the chain inverts by proportionality:
$$V_e^{target} = \frac{u^{*}}{u_z(0)\,/\,\Delta V_c}\; r_V, \qquad \Delta P^{target} = \frac{\Delta V_c^{target}}{\beta_c V_0}.$$

## Assumptions
Homogeneous isotropic elastic half-space with a flat surface; static, end-state response; ideal gas;
one connected reservoir per level; resident composition controls β_m, injected composition is a label;
the full-space spheroid compliance is used even for shallow sources (unquantified free-surface uncertainty
when a/d ≈ 1). A magmatic calculation at a source the authors interpret as hydrothermal is a hypothetical
end-member, not a reconstruction.
