#!/usr/bin/env python3
"""
quiz_from_json.py

用法示例:
    python quiz_from_json.py --json p1l1.json --splits_dir splits --out result.xlsx

功能:
- 读取 JSON（格式同你提供的 {"name":"...", "tag":"P1L1", "words":[{"index":19,"translate":"...","answer":["..."]}, ...]}）
- 播放对应音频（优先 splits/<tag>/<tag>_<index>.mp3）
- 等待用户输入；在按第一个字母时开始计时，按回车结束并判断是否正确
- 导出 XLSX，错误单元格背景红，错误字母黄色，正确字母黑色
"""

import os
import sys
import json
import time
import argparse
import subprocess
from typing import List, Tuple

# third-party
# pip install xlsxwriter
try:
    import xlsxwriter
except Exception as e:
    print("需要安装 xlsxwriter：pip install xlsxwriter")
    raise

# optional: pydub fallback for playback if ffplay not present
try:
    from pydub import AudioSegment
    from pydub.playback import _play_with_simpleaudio
    _HAVE_PYDUB = True
except Exception:
    _HAVE_PYDUB = False

# ---------- cross-platform single-line input with "start timing on first key" ----------
if os.name == "nt":
    import msvcrt

    def get_timed_input(prompt: str = "") -> Tuple[str, float]:
        """
        Windows implementation:
        Returns (text_entered, elapsed_seconds_from_first_key_to_enter)
        """
        sys.stdout.write(prompt)
        sys.stdout.flush()

        buf_chars = []
        started = False
        start_time = 0.0

        while True:
            ch = msvcrt.getwch()  # returns str
            if not started:
                # ignore initial special keys like '\x00' / '\xe0'
                started = True
                start_time = time.time()
            if ch == '\r':  # Enter
                sys.stdout.write("\n")
                break
            elif ch == '\x08':  # Backspace
                if buf_chars:
                    buf_chars.pop()
                    # move cursor back, overwrite, move back
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            else:
                buf_chars.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()

        elapsed = time.time() - start_time if started else 0.0
        return ''.join(buf_chars), elapsed

else:
    import tty
    import termios

    def get_timed_input(prompt: str = "") -> Tuple[str, float]:
        """
        Unix implementation using raw tty.
        Returns (text_entered, elapsed_seconds_from_first_key_to_enter)
        """
        sys.stdout.write(prompt)
        sys.stdout.flush()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        buf_chars = []
        started = False
        start_time = 0.0
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if not started:
                    started = True
                    start_time = time.time()
                # Enter (LF)
                if ch == '\r' or ch == '\n':
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                    break
                # Backspace (DEL or BS)
                if ch == '\x7f' or ch == '\b':
                    if buf_chars:
                        buf_chars.pop()
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                    continue
                # printable
                buf_chars.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        elapsed = time.time() - start_time if started else 0.0
        return ''.join(buf_chars), elapsed

# ---------- playback helpers ----------
def has_ffplay() -> bool:
    """检测系统是否有 ffplay"""
    try:
        subprocess.run(["ffplay", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def play_audio_async_ffplay(path: str):
    """使用 ffplay 异步播放（无窗口）"""
    # -nodisp 不显示视频窗口, -autoexit 结束后退出, -loglevel quiet 抑制日志
    try:
        proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc
    except Exception as e:
        return None

def play_audio_pydub_async(path: str):
    """使用 pydub + simpleaudio 播放（如果可用）"""
    if not _HAVE_PYDUB:
        return None
    try:
        seg = AudioSegment.from_file(path)
        play_obj = _play_with_simpleaudio(seg)
        return play_obj  # has stop() method
    except Exception:
        return None

def play_audio(path: str):
    """统一播放调用，返回一个可用于停止的对象或 None"""
    if has_ffplay():
        return play_audio_async_ffplay(path)
    else:
        return play_audio_pydub_async(path)

def stop_playback(obj):
    """尝试停止播放进程/对象"""
    if obj is None:
        return
    # ffplay returns subprocess.Popen
    if isinstance(obj, subprocess.Popen):
        try:
            obj.kill()
        except Exception:
            pass
    else:
        # pydub simpleaudio PlayObject
        try:
            obj.stop()
        except Exception:
            pass

# ---------- comparison / per-letter coloring ----------
def simple_compare_and_color(user: str, target: str) -> List[Tuple[str, bool]]:
    """
    简单逐字符比较：
    返回 list of (char, is_correct_bool)
    规则：
      - 将 user 和 target 都视为小写比较，但保留原用户字符用于显示
      - 对齐方式：逐位比较，若长度不同，超出部分均视为错误
    该函数不做复杂编辑距离对齐（可按需增强）
    """
    u = user
    t = target
    res = []
    n = max(len(u), len(t))
    for i in range(n):
        uc = u[i] if i < len(u) else ''
        tc = t[i] if i < len(t) else ''
        if uc != '':
            is_correct = (uc.lower() == tc.lower())
            res.append((uc, is_correct))
        else:
            # 用户没输入但目标有 -> we'll mark as missing (wrong) with placeholder
            res.append(('', False))
    return res

# ---------- writing excel ----------
def write_results_xlsx(out_path: str, tag: str, results: List[dict]):
    """
    results: list of dicts:
      {
        "index": int,
        "user": str,
        "target": str,
        "translate": str,
        "time": float,
        "correct": bool
      }
    """
    wb = xlsxwriter.Workbook(out_path)
    ws = wb.add_worksheet("results")

    # formats
    header_fmt = wb.add_format({"bold": True})
    wrong_cell_fmt = wb.add_format({"bg_color": "#FFCCCC"})  # red-ish
    normal_cell_fmt = wb.add_format()
    yellow_fmt = wb.add_format({"font_color": "yellow"})
    black_fmt = wb.add_format({"font_color": "black"})

    # headers
    ws.write(0, 0, "Index", header_fmt)
    ws.write(0, 1, "Your answer", header_fmt)
    ws.write(0, 2, "", header_fmt)
    ws.write(0, 3, "Time (s)", header_fmt)
    ws.write(0, 4, "Translate", header_fmt)

    row = 1
    for r in results:
        ws.write_number(row, 0, r["index"])
        user_text = r["user"] if r["user"] else ""
        target_text = r["target"] if r["target"] else ""
        cmp = simple_compare_and_color(user_text, target_text)

        if r["correct"]:
            ws.write(row, 1, user_text, normal_cell_fmt)
        else:
            # 红底整格
            red_bg_fmt = wb.add_format({"bg_color": "#FFCCCC"})
            black_fmt = wb.add_format({"bg_color": "#FFCCCC", "font_color": "black"})
            yellow_fmt = wb.add_format({"bg_color": "#FFCCCC", "font_color": "red"})

            if len(cmp) == 0:
                # 用户未输入
                ws.write(row, 1, "▯", red_bg_fmt)
            else:
                rich_items = []
                for i, (ch, ok) in enumerate(cmp):
                    if i == 0:
                        # 第一个字符使用红底 + 字体颜色
                        fmt = wb.add_format({"bg_color": "#FFCCCC", "font_color": "black" if ok else "red"})
                    else:
                        # 后续字符只设置字体颜色
                        fmt = black_fmt if ok else yellow_fmt
                    rich_items.append(fmt)
                    rich_items.append(ch if ch != '' else '-')

                # write_rich_string 至少要 2 格式+字符串
                if len(rich_items) < 4:
                    rich_items = [black_fmt, " "] + rich_items

                try:
                    ws.write_rich_string(row, 1, *rich_items)
                except Exception:
                    # fallback
                    ws.write(row, 1, user_text if user_text else "-", red_bg_fmt)

        # column 2 left blank
        ws.write(row, 2, "")
        # time
        ws.write_number(row, 3, round(r["time"], 3))
        # translate
        ws.write(row, 4, r["translate"])
        row += 1

    # set some column widths
    ws.set_column(0, 0, 10)
    ws.set_column(1, 1, 30)
    ws.set_column(3, 3, 12)
    ws.set_column(4, 4, 30)

    wb.close()


# ---------- main quiz flow ----------
def find_audio_path(splits_dir: str, tag: str, idx: int) -> str:
    """
    找到音频文件的路径，顺序尝试：
      1) splits_dir/tag/{tag}_{idx}.mp3
      2) splits_dir/tag/output_{idx}.mp3
      3) splits_dir/output_{idx}.mp3
      4) splits_dir/{tag}_{idx}.mp3
    返回第一个存在的路径，找不到返回 None
    """
    candidates = [
        os.path.join(splits_dir, tag, f"{tag}_{idx}.mp3"),
        os.path.join(splits_dir, tag, f"output_{idx}.mp3"),
        os.path.join(splits_dir, f"output_{idx}.mp3"),
        os.path.join(splits_dir, f"{tag}_{idx}.mp3"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    return "".join(s.split()).lower()

import datetime
import json
import os

def run_quiz(json_path: str, splits_dir: str, out_xlsx: str, play_audio_flag: bool = True):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tag = data.get("tag", "")
    name = data.get("name", "")
    words = data.get("words", [])

    results = []
    mistakes = []
    print("Starting quiz. Press Ctrl+C to abort any time.\n")

    for entry in words:
        idx = entry.get("index")
        translate = entry.get("translate", "")
        answers = entry.get("answer", [])  # list of acceptable spellings
        canonical = answers[0] if answers else ""

        audio_path = find_audio_path(splits_dir, tag, idx)
        if audio_path is None:
            print(f"[{idx}] audio not found. Skipping.")
            results.append({"index": idx, "user": "", "target": canonical, "translate": translate, "time": 0.0, "correct": False})
            mistakes.append(entry)
            continue

        print(f"\n[{idx}] Playing: {audio_path}")
        playback_obj = play_audio(audio_path) if play_audio_flag else None

        try:
            prompt = f"Type the spelling for index {idx}: "
            user_text, elapsed = get_timed_input(prompt)
        except KeyboardInterrupt:
            print("\nAborted by user.")
            stop_playback(playback_obj)
            break

        stop_playback(playback_obj)

        user_norm = normalize_text(user_text)
        correct_norms = [normalize_text(a) for a in answers]
        is_correct = (user_norm in correct_norms)

        if is_correct:
            print(f"✅ Correct! Time: {elapsed:.3f}s")
        else:
            print(f"❌ Wrong. Your input: '{user_text}' | expected: {answers} | Time: {elapsed:.3f}s")
            mistakes.append(entry)

        results.append({
            "index": idx,
            "user": user_text,
            "target": canonical,
            "translate": translate,
            "time": elapsed,
            "correct": is_correct
        })

    # write xlsx
    print(f"\nWriting results to {out_xlsx} ...")
    write_results_xlsx(out_xlsx, tag, results)
    print("Done.")

    # 输出错词 json
    if mistakes:
        timestamp = datetime.datetime.now().strftime("%m_%d_%H_%M")
        mistake_filename = f"mistake_{tag}_{timestamp}.json"
        mistake_data = {"name": name, "tag": tag, "words": mistakes}
        with open(mistake_filename, "w", encoding="utf-8") as f:
            json.dump(mistake_data, f, ensure_ascii=False, indent=2)
        print(f"Written {len(mistakes)} mistakes to {mistake_filename}")

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Quiz from JSON and audio files; export results to XLSX")
    parser.add_argument("--json", required=True, help="Input JSON file (the parsed wordlist)")
    parser.add_argument("--splits_dir", default="splits", help="Base splits directory")
    parser.add_argument("--out", default="quiz_results.xlsx", help="Output xlsx file")
    parser.add_argument("--no_play", action="store_true", help="Do not play audio (useful for debugging)")
    args = parser.parse_args()

    run_quiz(args.json, args.splits_dir, args.out, play_audio_flag=not args.no_play)

if __name__ == "__main__":
    main()
