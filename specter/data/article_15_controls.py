"""EU AI Act Article 15 controls — accuracy, robustness, cybersecurity.

Article 15 is the high-risk AI system obligation for "appropriate levels
of accuracy, robustness and cybersecurity, and that they perform
consistently in those respects throughout their lifecycle"
(Regulation (EU) 2024/1689, Article 15(1)).

This module structures the 8 canonical controls (C.1.1 through C.1.8)
that operationalise Article 15. Each control maps to a sub-paragraph
of the article (15(1) / 15(3) / 15(4) / 15(5)) and carries the
regulator-grounded citation text. Controls are read-only data — engines
that need to ground LLM output against Article 15 import these
constants directly.

Source: Regulation (EU) 2024/1689 (EU AI Act), 13 June 2024.
        https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689#art_15
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

_EUR_LEX_URL: Final = (
    "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689"
)


class Article15Control(BaseModel):
    """One Article 15 control row.

    Each control is anchored to a specific sub-paragraph of Article 15.
    ``citation`` is the regulator-verbatim text — used as grounding for
    LLM-backed retrievers so they can cite exactly without hallucinating
    new requirements.
    """

    control_id: str = Field(description="Canonical id, e.g. ``C.1.1``.")
    name: str = Field(description="Short control name.")
    objective: str = Field(description="What the control ensures.")
    article_ref: str = Field(
        description="Internal-form Article 15 sub-paragraph reference."
    )
    paragraph: str = Field(
        description="The sub-paragraph number for grouping (e.g. ``1``, ``3``)."
    )
    citation: str = Field(
        description="Verbatim text from the regulation grounding this control."
    )
    eur_lex_url: str = Field(default=_EUR_LEX_URL)


# ─── The 8 controls ────────────────────────────────────────────────────────


ARTICLE_15_CONTROLS: tuple[Article15Control, ...] = (
    Article15Control(
        control_id="C.1.1",
        name="Accuracy",
        objective="Ensure appropriate level of accuracy.",
        article_ref="Art. 15(1)",
        paragraph="1",
        citation=(
            "High-risk AI systems shall be designed and developed in such a way "
            "that they achieve an appropriate level of accuracy, robustness, and "
            "cybersecurity, and that they perform consistently in those respects "
            "throughout their lifecycle."
        ),
    ),
    Article15Control(
        control_id="C.1.2",
        name="Robustness",
        objective="Ensure appropriate level of robustness.",
        article_ref="Art. 15(1)",
        paragraph="1",
        citation=(
            "High-risk AI systems shall be designed and developed in such a way "
            "that they achieve an appropriate level of accuracy, robustness, and "
            "cybersecurity, and that they perform consistently in those respects "
            "throughout their lifecycle."
        ),
    ),
    Article15Control(
        control_id="C.1.3",
        name="Cybersecurity",
        objective="Ensure appropriate level of cybersecurity.",
        article_ref="Art. 15(1)",
        paragraph="1",
        citation=(
            "High-risk AI systems shall be designed and developed in such a way "
            "that they achieve an appropriate level of accuracy, robustness, and "
            "cybersecurity, and that they perform consistently in those respects "
            "throughout their lifecycle."
        ),
    ),
    Article15Control(
        control_id="C.1.4",
        name="Consistent Performance",
        objective=(
            "Ensure consistent accuracy, robustness and cybersecurity across "
            "the AI system lifecycle."
        ),
        article_ref="Art. 15(1)",
        paragraph="1",
        citation=(
            "High-risk AI systems shall be designed and developed in such a way "
            "that they achieve an appropriate level of accuracy, robustness, and "
            "cybersecurity, and that they perform consistently in those respects "
            "throughout their lifecycle."
        ),
    ),
    Article15Control(
        control_id="C.1.5",
        name="Accuracy Transparency",
        objective="Ensure that accuracy metrics are declared in the instructions of use.",
        article_ref="Art. 15(3)",
        paragraph="3",
        citation=(
            "The levels of accuracy and the relevant accuracy metrics of high-risk "
            "AI systems shall be declared in the accompanying instructions of use."
        ),
    ),
    Article15Control(
        control_id="C.1.6",
        name="Resiliency",
        objective=(
            "Ensure the AI system is as resilient as possible regarding errors, "
            "faults and inconsistencies."
        ),
        article_ref="Art. 15(4)",
        paragraph="4",
        citation=(
            "High-risk AI systems shall be as resilient as possible regarding errors, "
            "faults or inconsistencies that may occur within the system or the "
            "environment in which the system operates, in particular due to their "
            "interaction with natural persons or other systems. Technical and "
            "organisational measures shall be taken in this regard. The robustness of "
            "high-risk AI systems may be achieved through technical redundancy "
            "solutions, which may include backup or fail-safe plans."
        ),
    ),
    Article15Control(
        control_id="C.1.7",
        name="Biased Feedback Loops",
        objective=(
            "Eliminate or reduce as far as possible biased outputs influencing "
            "input for future operations."
        ),
        article_ref="Art. 15(4)",
        paragraph="4",
        citation=(
            "High-risk AI systems that continue to learn after being placed on the "
            "market or put into service shall be developed in such a way as to "
            "eliminate or reduce as far as possible the risk of possibly biased "
            "outputs influencing input for future operations (feedback loops), and as "
            "to ensure that any such feedback loops are duly addressed with "
            "appropriate mitigation measures."
        ),
    ),
    Article15Control(
        control_id="C.1.8",
        name="Malicious actors",
        objective=(
            "Ensure resilience against unauthorised attempts to alter use, outputs, "
            "or performance via vulnerability exploitation (data poisoning, "
            "model poisoning, adversarial examples, confidentiality attacks)."
        ),
        article_ref="Art. 15(5)",
        paragraph="5",
        citation=(
            "High-risk AI systems shall be resilient against attempts by unauthorised "
            "third parties to alter their use, outputs or performance by exploiting "
            "system vulnerabilities. The technical solutions aiming to ensure the "
            "cybersecurity of high-risk AI systems shall be appropriate to the "
            "relevant circumstances and the risks. The technical solutions shall "
            "include, where appropriate, measures to prevent, detect, respond to, "
            "resolve and control for attacks trying to manipulate the training data "
            "set (data poisoning), or pre-trained components used in training (model "
            "poisoning), inputs designed to cause the AI model to make a mistake "
            "(adversarial examples or model evasion), confidentiality attacks or "
            "model flaws."
        ),
    ),
)


# ─── Indexed lookups ───────────────────────────────────────────────────────


_BY_ID: Final[dict[str, Article15Control]] = {
    c.control_id: c for c in ARTICLE_15_CONTROLS
}


def get_control(control_id: str) -> Article15Control | None:
    """Return the control with this id, or None."""
    return _BY_ID.get(control_id)


def controls_for_paragraph(paragraph: str) -> list[Article15Control]:
    """Return all controls anchored to a given Article 15 sub-paragraph.

    ``paragraph`` is the bare digit (``"1"``, ``"3"``, ``"4"``, ``"5"``).
    Returns an empty list for unknown paragraphs.
    """
    return [c for c in ARTICLE_15_CONTROLS if c.paragraph == paragraph]


def all_paragraphs() -> tuple[str, ...]:
    """Return the unique sub-paragraph numbers covered by Article 15."""
    return tuple(sorted({c.paragraph for c in ARTICLE_15_CONTROLS}))


__all__ = [
    "ARTICLE_15_CONTROLS",
    "Article15Control",
    "all_paragraphs",
    "controls_for_paragraph",
    "get_control",
]
