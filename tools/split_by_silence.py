#!/usr/bin/env python3
import os
import argparse
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor, as_completed

def analyze_chunk(audio, start, end, silence_thresh):
    """检测某一段是否为静音"""
    segment = audio[start:end]
    return (start, end, segment.dBFS < silence_thresh)

def split_by_silence_fast(input_path, silence_thresh=-45.0, min_silence_len=200, output_dir="splits",
                          keep_silence=100, chunk_ms=20, max_workers=8, min_active_len=100):
    print(f"Loading {input_path} ...")
    audio = AudioSegment.from_file(input_path)
    total_ms = len(audio)
    print(f"Audio length: {total_ms/1000:.2f}s")

    os.makedirs(output_dir, exist_ok=True)

    # 并行检测每个小块响度
    print("Analyzing silence using multi-threading ...")
    silent_mask = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(analyze_chunk, audio, i, min(i+chunk_ms, total_ms), silence_thresh)
                   for i in range(0, total_ms, chunk_ms)]
        for fut in as_completed(futures):
            silent_mask.append(fut.result())
    # 排序结果
    silent_mask.sort(key=lambda x: x[0])

    # 找连续静音区间
    silent_ranges = []
    current_start = None
    for start, end, is_silent in silent_mask:
        if is_silent:
            if current_start is None:
                current_start = start
        else:
            if current_start is not None:
                if end - current_start >= min_silence_len:
                    silent_ranges.append((current_start, end))
                current_start = None
    if current_start is not None and total_ms - current_start >= min_silence_len:
        silent_ranges.append((current_start, total_ms))

    print(f"Detected {len(silent_ranges)} silence ranges")

    # 计算切割区间
    boundaries = []
    prev_end = 0
    for start, end in silent_ranges:
        if start - prev_end >= min_active_len:
            boundaries.append((prev_end, start))
        prev_end = end
    if total_ms - prev_end >= min_active_len:
        boundaries.append((prev_end, total_ms))

    # 导出每段
    count = 0
    for st, ed in boundaries:
        st2 = max(0, st - keep_silence)
        ed2 = min(total_ms, ed + keep_silence)
        chunk = audio[st2:ed2]

        # 跳过几乎全静音的片段
        if chunk.dBFS < silence_thresh + 5:
            continue

        out_path = os.path.join(output_dir, f"output_{count}.mp3")
        chunk.export(out_path, format="mp3")
        print(f"[{count}] {out_path}  ({(ed2-st2)/1000:.2f}s, {chunk.dBFS:.1f} dB)")
        count += 1

    print(f"✅ Done. Exported {count} valid segments to '{output_dir}/'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fast audio splitter using silence detection (multithreaded)")
    parser.add_argument("input", help="Input audio file path")
    parser.add_argument("--threshold", type=float, default=-45.0, help="Silence threshold in dBFS (default -45)")
    parser.add_argument("--minlen", type=int, default=200, help="Minimum silence length in ms (default 700)")
    parser.add_argument("--out", default="splits", help="Output folder")
    parser.add_argument("--keepsilence", type=int, default=100, help="Keep this many ms of silence around cuts (default 100)")
    parser.add_argument("--workers", type=int, default=8, help="Threads for analysis (default 8)")
    parser.add_argument("--minactive", type=int, default=100, help="Minimum non-silent segment length to keep (default 200 ms)")
    args = parser.parse_args()

    split_by_silence_fast(
        input_path=args.input,
        silence_thresh=args.threshold,
        min_silence_len=args.minlen,
        output_dir=args.out,
        keep_silence=args.keepsilence,
        max_workers=args.workers,
        min_active_len=args.minactive
    )
