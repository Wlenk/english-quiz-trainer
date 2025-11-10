#!/usr/bin/env python3
# parse_wordlist.py
# 用途：从格式混乱的 txt 中解析出编号、英文答案（可多个）和中文释义，输出 JSON。
# 兼容 Python 3.8+

import re
import json
import argparse
from typing import List, Dict

# 用于识别 CJK（汉字、平假名、片假名、韩文）区间
_CJK_RANGE = r'\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af'

def normalize_space_between_cjk_and_latin(text: str) -> str:
    """
    在中日韩字符与拉丁字母/数字/括号之间插入空格，方便后续正则分割。
    例如 "advancedlevel高级水平" -> "advancedlevel 高级水平"
    """
    # latin followed by CJK
    text = re.sub(r'([A-Za-z0-9\)\]\}])([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af])', r'\1 \2', text)
    # CJK followed by latin
    text = re.sub(r'([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af])([A-Za-z0-9\(\[\{])', r'\1 \2', text)
    # collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def split_into_entries(full_text: str) -> List[Dict]:
    """
    使用数字序号（如 '55.'）作为条目拆分锚点。
    返回 list of dict: {'index': int, 'body': str}
    """
    # 先标准化一些不可见字符
    txt = full_text.replace('\r\n', '\n').replace('\r', '\n')
    txt = normalize_space_between_cjk_and_latin(txt)

    # 找到所有 "NN." 的位置
    marker_re = re.compile(r'(?m)(\d{1,4})\.\s*')
    matches = list(marker_re.finditer(txt))

    entries = []
    if not matches:
        # 如果没有找到任何编号，尝试将整块文本做为一个条目（index=1）
        body = txt.strip()
        if body:
            entries.append({'index': 1, 'body': body})
        return entries

    for i, m in enumerate(matches):
        idx = int(m.group(1))
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(txt)
        body = txt[start:end].strip()
        entries.append({'index': idx, 'body': body})
    return entries

def extract_translate_and_answers(body: str):
    body = body.strip(' .-–—')
    # 找中文部分
    cjk_re = re.compile(r'[' + _CJK_RANGE + r']+')
    m = cjk_re.search(body)
    translate = m.group(0).strip() if m else ""

    # 去括号
    no_paren = re.sub(r'\([^)]*\)', ' ', body)
    # 抽取所有英文串
    eng_re = re.compile(r'\b[A-Za-z][A-Za-z\'\- ]*[A-Za-z]\b')
    found = eng_re.findall(no_paren)
    # 拆分斜杠内的变体
    answers = []
    for token in found:
        parts = re.split(r'[\/,]', token)
        for p in parts:
            p = p.strip()
            if len(p) < 2:
                continue
            if re.fullmatch(r'[A-Za-z][A-Za-z\'\- ]*[A-Za-z]', p):
                answers.append(p)
    # 去重
    seen, uniq = set(), []
    for a in answers:
        if a.lower() not in seen:
            seen.add(a.lower())
            uniq.append(a)
    return translate, uniq

def build_json(name: str, tag: str, entries: List[Dict]) -> Dict:
    words = []
    for e in entries:
        idx = e['index']
        body = e['body']
        translate, answers = extract_translate_and_answers(body)
        words.append({
            "index": idx,
            "translate": translate,
            "answer": answers
        })
    # 按 index 排序并去重 index（如果有重复，只保留第一个）
    words.sort(key=lambda x: x['index'])
    seen_idx = set()
    cleaned = []
    for w in words:
        if w['index'] in seen_idx:
            continue
        seen_idx.add(w['index'])
        cleaned.append(w)

    # ✅ 重新从 1 开始编号
    for new_idx, w in enumerate(cleaned, start=1):
        w['index'] = new_idx

    return {"name": name, "tag": tag, "words": cleaned}

def main():
    parser = argparse.ArgumentParser(description="Parse a messy numbered wordlist txt into JSON.")
    parser.add_argument("input", help="Input txt file")
    parser.add_argument("--name", required=True, help="Name for JSON field 'name' (e.g. 'Part 1 Word List 1')")
    parser.add_argument("--tag", required=True, help="Tag for JSON field 'tag' (e.g. 'P1L1')")
    parser.add_argument("--output", default="words.json", help="Output JSON file (default words.json)")
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        txt = f.read()

    entries = split_into_entries(txt)
    result = build_json(args.name, args.tag, entries)

    # write JSON pretty
    with open(args.output, 'w', encoding='utf-8') as fo:
        json.dump(result, fo, ensure_ascii=False, indent=2)

    print(f"Parsed {len(result['words'])} entries -> '{args.output}'")

if __name__ == "__main__":
    main()
