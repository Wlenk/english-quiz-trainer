import json
import os
import genanki
import shutil
import datetime

def json_to_apkg(json_path, splits_dir, out_apkg):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tag = data.get("tag", "")
    name = data.get("name", "Deck")
    words = data.get("words", [])

    # 创建 Deck
    deck_id = int(datetime.datetime.now().timestamp())
    deck = genanki.Deck(deck_id, name)

    # 创建 Note Model
    model_id = deck_id + 1
    model = genanki.Model(
        model_id,
        'Basic Model',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[{
                'name': 'Spelling Card',
                'qfmt': '{{Front}}<br><hr><br>{{type:Front}}',
                'afmt': '{{Front}}<hr>{{Back}}',
            },
        ])

    media_files = []

    for entry in words:
        index = entry.get("index")
        translate = entry.get("translate", "")
        answers = entry.get("answer", [])
        if not answers:
            continue
        front = answers[0]

        # 音频文件
        audio_file = f"{tag}_{index}.mp3"
        audio_path = os.path.join(splits_dir, tag, audio_file)
        if os.path.exists(audio_path):
            front_with_audio = f'[sound:{audio_file}]'
            media_files.append(audio_path)
        else:
            front_with_audio = front
        translate = f'{translate} {front}'

        note = genanki.Note(
            model=model,
            fields=[front_with_audio, translate],
            tags=[tag]
        )
        deck.add_note(note)

    # 创建包
    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(out_apkg)
    print(f"✅ .apkg 文件生成完成: {out_apkg}")
    print(f"包含 {len(words)} 个单词，音频文件 {len(media_files)} 个")

# 示例
if __name__ == "__main__":
    json_path = "words.json"
    splits_dir = "splits"
    out_apkg = "P1.apkg"
    json_to_apkg(json_path, splits_dir, out_apkg)
