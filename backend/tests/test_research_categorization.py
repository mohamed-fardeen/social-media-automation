from app.api.v1.research import _build_research_rows
from app.schemas.research_plan import ResearchDocument


def _doc(title: str, content: str, url: str = "https://example.com/article") -> ResearchDocument:
    return ResearchDocument(
        id=title.lower().replace(" ", "-"),
        title=title,
        url=url,
        content=content,
        provider="tavily",
        platform="web",
    )


def _rows(docs, competitors=None):
    return _build_research_rows(
        docs,
        company="Atlas",
        topic="construction 3D printing",
        industry="construction 3D printing",
        competitors=competitors or [],
        now="2026-08-12T00:00:00+00:00",
    )


def test_competitor_entity_is_extracted_from_source_without_classifying_source_as_competitor():
    rows = _rows([
        _doc(
            "Architecture site covers ICON home project",
            "ICON announced a new 3D printed home project using concrete 3D printing in Texas.",
        )
    ])

    competitor_rows = [row for row in rows if row["source_kind"] == "competitor"]
    assert [row["title"] for row in competitor_rows] == ["ICON"]
    assert any(row["source_kind"] == "trend" and "ICON home project" in row["title"] for row in rows)


def test_reference_sources_are_not_trends_or_competitors():
    rows = _rows([
        _doc(
            "3D concrete printing - Wikipedia",
            "Wikipedia overview and definition of 3D concrete printing and additive construction.",
            "https://en.wikipedia.org/wiki/3D_concrete_printing",
        )
    ])

    assert [row["source_kind"] for row in rows] == ["reference"]


def test_out_of_scope_large_scale_robotics_is_excluded():
    rows = _rows([
        _doc(
            "Large scale robotics in warehouses",
            "A new warehouse robot arm improves pallet handling and logistics automation.",
        )
    ])

    assert rows == []


def test_industry_list_discovers_competitors_without_classifying_article_as_competitor():
    rows = _rows([
        _doc(
            "Top construction 3D printing companies",
            "This industry article lists construction 3D printing companies including COBOD, ICON, and CyBe.",
        )
    ])

    assert {row["title"] for row in rows if row["source_kind"] == "competitor"} == {"COBOD", "ICON", "CyBe"}
    assert any(row["source_kind"] == "reference" and row["title"] == "Top construction 3D printing companies" for row in rows)


def test_duplicate_sources_count_same_company_once():
    rows = _rows([
        _doc("ICON project one", "ICON launched a new 3D printed house using concrete 3D printing."),
        _doc("ICON project two", "Another article says ICON expanded a construction 3D printing project."),
    ])

    assert [row["title"] for row in rows if row["source_kind"] == "competitor"] == ["ICON"]
