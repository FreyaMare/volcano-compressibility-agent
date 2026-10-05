# Changelog

## 1.0.0 — 2026-10-05
First release.

* Literature-research agent (Claude API, web search and page fetch) in three stages: volcanic system,
  unrest and geodesy, petrology of each magma. Every input carries value, range, source and status (M/U/A/D).
* Seven-step chain of the La Fossa thesis generalised to any volcano: EVo volatile equilibria, frozen and
  equilibrium magma compressibility, sphere / prolate spheroid / penny-crack chamber compressibility, r_V,
  Mogi / Yang / Fialko uplift; inverse analysis, overpressure screen, thin-crack check, verification and
  consistency checks, sensitivity analyses (Scenario B, pressure datum x H2O, density, redox, aspect ratio, mu, nu).
* Thesis-style PDF report with model-written chapters and an automatic number audit.
* Streamlit app (with data review/editing and owner-key protection) and Google Colab notebook.
* Regression test: the La Fossa reference dataset reproduces every r_V and uplift value of the thesis.
* Robustness: unit and range checks on every input, tolerant parsing of the agent's answers, cracks wider than deep
  excluded, deflation sources handled, calculation caveats reported in Section 4.7; edge-case test suite.
* EVo: its temperature-range warning (invalid format string in the pinned commit) is replaced so that EVo continues
  with temperature-independent solubility coefficients as intended; such states are flagged.
* Claude API: automatic prompt caching, forced structured output for the writer, recovery from truncated answers,
  retries honouring retry-after.
