import os
import re
import argparse

def rename_audio_segments(folder):
    pattern = re.compile(r"output_(\d+)\.mp3$")
    files = [f for f in os.listdir(folder) if pattern.match(f)]
    if not files:
        print("❌ No matching files found in folder.")
        return

    # 提取编号并排序
    files_with_numbers = [(int(pattern.match(f).group(1)), f) for f in files]
    files_with_numbers.sort(key=lambda x: x[0])

    print(f"Found {len(files_with_numbers)} files. Renaming...")

    temp_map = []
    for i, (_, filename) in enumerate(files_with_numbers, start=1):
        src = os.path.join(folder, filename)
        tmp = os.path.join(folder, f"tmp_{i}.mp3")
        os.rename(src, tmp)
        temp_map.append(tmp)

    # 再重命名为连续编号
    for i, tmp in enumerate(temp_map, start=1):
        dst = os.path.join(folder, f"P1L4L5L6_{i}.mp3")
        os.rename(tmp, dst)
        print(f"Renamed → {os.path.basename(dst)}")

    print("✅ All files renamed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Renumber split audio files sequentially.")
    parser.add_argument("--dir", default="splits", help="Directory containing split mp3 files")
    args = parser.parse_args()

    rename_audio_segments(args.dir)
