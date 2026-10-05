"""End-to-end orchestration: volcano name -> literature research -> seven-step chain ->
thesis-style PDF report."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from .chain import Analysis
from .defaults import finalize
from .facts import build_facts
from .llm import DEFAULT_MODEL, Usage
from .report_pdf import audit_chapters, build_pdf
from .schema import Dataset

REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "reference")


@dataclass
class RunResult:
    dataset: Dataset
    analysis: Analysis
    results: dict
    facts: dict
    chapters: dict
    pdf: bytes
    log: list = field(default_factory=list)

    def dataset_json(self) -> str:
        return self.dataset.model_dump_json(indent=1)


def load_reference(name: str = "lafossa") -> Dataset:
    with open(os.path.join(REFERENCE_DIR, f"{name}.json")) as f:
        return Dataset.model_validate_json(f.read())


def research(volcano: str, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
             depth: str = "standard", on_event: Callable[[str], None] | None = None) -> tuple[Dataset, Usage]:
    from .research import research_volcano
    return research_volcano(volcano, api_key=api_key, model=model, on_event=on_event, depth=depth)


def analyse_and_report(ds: Dataset, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                       target_mm: float = 10.0, screen_MPa: float = 10.0, use_evo: bool = True,
                       write: bool = True, usage: Usage | None = None,
                       on_event: Callable[[str], None] | None = None) -> RunResult:
    """Finalise a (researched or edited) dataset, run the chain, write and build the PDF."""
    log: list = []

    def say(s):
        log.append(s)
        if on_event:
            on_event(s)

    usage = usage or Usage()
    ds = finalize(Dataset.model_validate(ds.model_dump()))       # work on a copy
    say(f"Dataset ready: {len(ds.magmas)} magmas, {len(ds.levels)} storage levels, "
        f"{'a published' if ds.deformation_source else 'no'} deformation source, {len(ds.data_gaps)} flagged gaps")
    an = Analysis(ds, use_evo=use_evo, log=say)
    R = an.run_all(target_mm=target_mm, screen_MPa=screen_MPa, progress=say)
    facts = build_facts(ds, R)
    from .writer import offline_chapters
    chapters = None
    if write and (api_key or os.environ.get("ANTHROPIC_API_KEY")):
        from .writer import write_chapters
        try:
            chapters = write_chapters(ds, facts, api_key=api_key, model=model, on_event=say, usage=usage)
        except Exception as err:            # the computed report is still worth delivering
            say(f"Writing the chapters failed ({type(err).__name__}: {str(err)[:160]}); "
                "the report is built with placeholder text instead")
    else:
        say("No API key: narrative chapters replaced by a factual placeholder")
    if chapters is None:
        chapters = offline_chapters(ds, facts)
    audit = audit_chapters(chapters, {"facts": facts, "notes": ds.narrative})
    if audit:
        say(f"Number audit: {len(audit)} number(s) in the text not matched to the computed facts (listed in Appendix C)")
    say("Building the PDF report")
    pdf = build_pdf(ds, an, R, facts, chapters,
                    meta=dict(model=model, usage=usage.summary() if usage.calls else "offline", audit=audit))
    return RunResult(ds, an, R, facts, chapters, pdf, log)


def run_agent(volcano: str, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, depth: str = "standard",
              target_mm: float = 10.0, on_event: Callable[[str], None] | None = None) -> RunResult:
    """The whole agent in one call."""
    raw, usage = research(volcano, api_key=api_key, model=model, depth=depth, on_event=on_event)
    return analyse_and_report(raw, api_key=api_key, model=model, target_mm=target_mm, usage=usage, on_event=on_event)


if __name__ == "__main__":                       # python -m volcano_agent.pipeline "Mount Etna"
    import sys
    name = " ".join(sys.argv[1:]) or "La Fossa"
    if name.lower().startswith("lafossa-offline"):
        rr = analyse_and_report(load_reference("lafossa"), write=False, on_event=print)
    else:
        rr = run_agent(name, on_event=print)
    out = f"{rr.dataset.slug}_report.pdf"
    with open(out, "wb") as f:
        f.write(rr.pdf)
    with open(f"{rr.dataset.slug}_dataset.json", "w") as f:
        f.write(rr.dataset_json())
    print("wrote", out)
