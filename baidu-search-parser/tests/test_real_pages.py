"""Tests against excerpt fixtures of the measured pages (2026-10-25).

Expected values were fixed by manual DOM inspection of the original
HTML (see ../parser-validation.md), not by accepting parser output.
"""

import json

import pytest

from conftest import parse_fixture


# ---------------------------------------------------------------- counts

@pytest.mark.parametrize(
    "name,organic,ads,cards,unknown,c_results",
    [
        ("tianqi_p1.html", 5, 0, 4, 0, 11),
        ("tianqi_pn10.html", 6, 0, 4, 0, 12),
        ("tianqi_pn20.html", 8, 0, 0, 0, 10),
        ("sapporo.html", 7, 0, 2, 0, 11),
        ("weather_en.html", 3, 0, 6, 0, 11),
    ],
)
def test_classification_counts(name, organic, ads, cards, unknown, c_results):
    page = parse_fixture(name)
    assert page.diagnostics["c_result_count"] == c_results
    assert len(page.results) == organic
    assert len(page.ads) == ads
    assert len(page.cards) == cards
    assert len(page.unknown_elements) == unknown


def test_card_kinds():
    kinds = [c.card_kind for c in parse_fixture("tianqi_p1.html").cards]
    assert kinds == ["weather", "knowledge_graph", "note", "official_account"]
    kinds = [c.card_kind for c in parse_fixture("tianqi_pn10.html").cards]
    assert kinds == ["baike", "baike", "forum", "live"]
    kinds = [c.card_kind for c in parse_fixture("weather_en.html").cards]
    assert kinds == ["dictionary", "knowledge_graph", "video", "note", "video", "baike"]
    kinds = [c.card_kind for c in parse_fixture("sapporo.html").cards]
    assert kinds == ["ai_answer", "note"]


# ---------------------------------------------------------------- organic fields

def test_tianqi_first_result():
    r = parse_fixture("tianqi_p1.html").results[0]
    assert r.organic_rank == 1
    assert r.display_position == 3
    assert r.title == "WEB 应用防火墙"
    assert r.url == "http://weather.cma.cn/"
    assert r.url_source == "data_log.mu"
    assert r.domain == "weather.cma.cn"
    assert r.display_url == "weather.cma.cn"
    assert r.site_name == "中国气象局"
    assert r.snippet is not None and r.snippet.startswith("当前正在对访问请求进行人机识别检测")
    assert [s.text for s in r.sitelinks] == ["南京", "黑牛城", "南宁", "沙坪坝"]
    assert r.is_baidu_redirect is True
    assert r.click_url_kind == "baidu_redirect"


def test_tianqi_titles_and_dates():
    results = parse_fixture("tianqi_p1.html").results
    assert "2026天马参赛指南来了" in results[1].title
    assert results[1].date == "10月25日"
    assert results[1].date_source == "source_sdata"
    assert results[2].title == "天气网"
    assert results[2].url == "https://www.weather.com.cn/?u3wwy=67351"
    assert results[3].title.startswith("【大自然天气预报15天")
    assert "将减弱为温带气旋" in results[4].title


def test_snippet_date_prefix_separated():
    # pn10 order=7: the "4小时前" label is a prefix-time element and must
    # not leak into the snippet; the date comes from source s-data.
    page = parse_fixture("tianqi_pn10.html")
    r = [x for x in page.results if x.display_position == 7][0]
    assert r.title == "...海洋天气公报-中华人民共和国交通运输部"
    assert r.site_name == "交通运输部"
    assert r.date == "10月25日"
    assert r.snippet.startswith("一、近海海域天气实况")
    assert not r.snippet.startswith("4小时前")


def test_www_specific_has_no_snippet():
    # www_specific layout ships no abstract module: snippet stays null.
    page = parse_fixture("tianqi_pn20.html")
    specific = [r for r in page.results if r.tpl == "www_specific"]
    assert len(specific) == 3
    assert all(r.snippet is None for r in specific)
    assert all(r.title for r in specific)


def test_display_order_and_ranks():
    page = parse_fixture("tianqi_pn20.html")
    positions = [r.display_position for r in page.results]
    assert positions == [1, 2, 3, 4, 5, 7, 8, 9]
    assert [r.organic_rank for r in page.results] == list(range(1, 9))
    # display order in the JSON follows the HTML order attribute order
    all_entries = sorted(
        [(e.display_position, e.position_in_page) for e in page.results]
    )
    assert [p for _, p in all_entries] == sorted(p for _, p in all_entries)


def test_japanese_page():
    page = parse_fixture("sapporo.html")
    titles = [r.title for r in page.results]
    assert titles[0].startswith("【札幌市天气预报15天")
    assert page.results[0].domain == "uc.weather.com.cn"
    # Japanese title text preserved verbatim
    assert "札幌市, 北海道の月間天気予報 - weather.com" in titles
    assert page.results[1].date == "10月20日"


def test_ai_answer_card():
    page = parse_fixture("sapporo.html")
    card = [c for c in page.cards if c.card_kind == "ai_answer"][0]
    assert card.ai_generated_marker is True
    # nourl.ubs.baidu.com placeholder in data-log.mu is not a content URL
    assert card.url is None
    # The generated answer body is not present in the static HTML
    assert card.text is None


def test_english_page():
    page = parse_fixture("weather_en.html")
    r = page.results[0]
    assert r.title == "weather - 搜索 词典"
    assert r.url == "https://cn.bing.com/dict/weather"
    dictionary = [c for c in page.cards if c.card_kind == "dictionary"][0]
    assert dictionary.title == "weather - 百度翻译"
    assert dictionary.url.startswith("https://fanyi.baidu.com/")
    kg = [c for c in page.cards if c.card_kind == "knowledge_graph"][0]
    assert kg.text is not None and kg.text.startswith("Weather是英语多词性词汇")
    video = [c for c in page.cards if c.card_kind == "video"][0]
    assert video.url == "https://www.bilibili.com/video/BV1VX4y1y7WV"


def test_knowledge_graph_text():
    page = parse_fixture("tianqi_p1.html")
    kg = [c for c in page.cards if c.card_kind == "knowledge_graph"][0]
    assert kg.text is not None and kg.text.startswith("天气，汉语词语")
    assert kg.url == "https://baike.baidu.com/item/%E5%A4%A9%E6%B0%94/332535"


# ---------------------------------------------------------------- pagination

def test_pagination_chain():
    p1 = parse_fixture("tianqi_p1.html").page
    assert (p1.pn, p1.page_number, p1.is_first_page) == (0, 1, True)
    assert p1.next_pn == 10 and p1.previous_url is None
    assert "pn=10" in p1.next_url and "word=%E5%A4%A9%E6%B0%94" in p1.next_url

    p2 = parse_fixture("tianqi_pn10.html").page
    assert (p2.pn, p2.page_number, p2.is_first_page) == (10, 2, False)
    assert p2.next_pn == 20 and p2.previous_pn == 0
    assert p2.next_url is not None and "pn=20" in p2.next_url
    assert p2.previous_url is not None

    p3 = parse_fixture("tianqi_pn20.html").page
    assert (p3.pn, p3.page_number) == (20, 3)
    assert p3.next_url is None and p3.next_pn is None
    assert p3.previous_pn == 10 and p3.first_url is not None


def test_no_cross_page_duplicates():
    seen = {}
    for name in ("tianqi_p1.html", "tianqi_pn10.html", "tianqi_pn20.html"):
        for r in parse_fixture(name).results:
            if r.url:
                assert r.url not in seen, f"duplicate url {r.url} in {name} and {seen[r.url]}"
                seen[r.url] = name


# ---------------------------------------------------------------- related

def test_related_searches():
    page = parse_fixture("tianqi_p1.html")
    queries = [r.query for r in page.related_searches]
    assert queries[0] == "没有广告的天气预报官方版"
    assert len(queries) == 10
    assert all(r.url for r in page.related_searches)
    sources = {r.source for r in page.related_searches}
    assert sources <= {"recommend_list", "page_relative"}


# ---------------------------------------------------------------- serialisation

@pytest.mark.parametrize(
    "name", ["tianqi_p1.html", "tianqi_pn10.html", "tianqi_pn20.html", "sapporo.html", "weather_en.html"]
)
def test_json_serialisable(name):
    data = parse_fixture(name).to_dict()
    text = json.dumps(data, ensure_ascii=False)
    assert json.loads(text) == data
    assert data["parser"]["name"] == "baidu_parser"
    assert data["diagnostics"]["warnings"] == []
