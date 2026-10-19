"""답변 초안 자동 점검기 (보너스)

LLM이 만든 답변 초안이
  1) 출력 규격(3단 구성 또는 [되묻기])을 지켰는지
  2) 근거 자료(규정 + 교육생 정보)에 없는 조항 번호를 인용했는지
  3) 근거 자료에 없는 금액·비율을 만들어 냈는지
를 규칙 기반으로 1차 점검한다. 사람이 최종 판정하기 전의 필터 용도다.

사용법:
  python3 bonus/check_output.py <근거자료.txt|md> <답변.md> [<답변.md> ...]
"""
import re
import sys
from pathlib import Path

SECTIONS = ["## 1. 답변 초안", "## 2. 근거 규정", "## 3. 확인 필요 항목"]
ARTICLE = re.compile(r"제\s*(\d+)\s*조")
MONEY = re.compile(r"(\d[\d,]*)\s*(만\s*원|원)")
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def split_sections(text):
    """답변 초안 / 근거 규정 / 확인 필요 항목 본문을 나눈다."""
    parts = {}
    for i, head in enumerate(SECTIONS):
        start = text.find(head)
        if start < 0:
            continue
        end = len(text)
        for nxt in SECTIONS[i + 1:]:
            pos = text.find(nxt)
            if pos > start:
                end = pos
                break
        parts[head] = text[start + len(head):end]
    return parts


def money_values(text):
    vals = set()
    for num, unit in MONEY.findall(text):
        n = int(num.replace(",", ""))
        vals.add(n * 10000 if "만" in unit else n)
    return vals


def computed_percents(source):
    """근거 자료의 정수들로 만들 수 있는 a/b*100 값(출석률 계산)도 허용한다."""
    nums = [int(n) for n in re.findall(r"(\d+)\s*일", source) if 0 < int(n) <= 31]
    allowed = set()
    for total in set(nums):
        for k in range(total + 1):
            allowed.add(round(k / total * 100, 1))
    return allowed


def check(source, answer):
    issues = []
    stripped = answer.strip()
    if stripped.startswith("[되묻기]"):
        n_q = len(re.findall(r"^\s*\d+\.", stripped, re.M))
        if n_q > 3:
            issues.append(f"되묻기 질문이 {n_q}개 (최대 3개)")
        return "되묻기", issues

    parts = split_sections(answer)
    missing = [h for h in SECTIONS if h not in parts]
    if missing:
        issues.append("누락된 섹션: " + ", ".join(missing))

    known_articles = set(ARTICLE.findall(source))
    draft = parts.get(SECTIONS[0], answer)
    # 답변 초안에서 근거 없는 조항을 "근거로" 쓰면 문제. 확인되지 않는다고 밝힌 문장은 허용.
    for sent in re.split(r"(?<=[.!?])\s+|\n", draft):
        for art in ARTICLE.findall(sent):
            if art not in known_articles and not re.search(r"확인되지|찾을 수 없|없습니다|없는", sent):
                issues.append(f"규정에 없는 제{art}조를 근거로 사용: {sent.strip()[:60]}")

    allowed_money = money_values(source)
    for v in money_values(draft) - allowed_money:
        issues.append(f"근거 자료에 없는 금액: {v:,}원")

    allowed_pct = {float(p) for p in PERCENT.findall(source)} | computed_percents(source)
    for p in PERCENT.findall(draft):
        if float(p) not in allowed_pct:
            issues.append(f"근거 자료로 계산할 수 없는 비율: {p}%")

    return "3단 구성", issues


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    bad = 0
    for path in sys.argv[2:]:
        kind, issues = check(source, Path(path).read_text(encoding="utf-8"))
        status = "OK  " if not issues else "WARN"
        bad += bool(issues)
        print(f"[{status}] {path} ({kind})")
        for msg in issues:
            print(f"        - {msg}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
