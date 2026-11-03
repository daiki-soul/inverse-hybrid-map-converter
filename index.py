import os
import re
import math
import pygetwindow as gw

SONGS_DIRECTORY = r"C:\Users\daiki\AppData\Local\osu!\Songs"

RELEASE_DIVISOR = 1.0
MIN_DIVISOR = 0.25


def find_osu_window_title():
    windows = gw.getWindowsWithTitle("")
    for window in windows:
        if window.title.lower().startswith("osu!"):
            return window.title
    return None


def extract_beatmap_name(title):
    cleaned_title = title.strip()
    without_brackets = re.sub(r"\s*\[[^\]]*\]\s*$", "", cleaned_title)
    parts = without_brackets.split(" - ")

    if len(parts) >= 3:
        return " - ".join(parts[2:]).strip()
    elif len(parts) == 2:
        return parts[1].strip()

    return without_brackets.strip()


def extract_difficulty_name(title):
    cleaned_title = title.strip()
    matches = re.findall(r"\[([^\]]+)\]", cleaned_title)

    if matches:
        return matches[-1].strip()

    return None


def find_osu_file_path(beatmap_name, difficulty_name, songs_directory):
    title_matches = []

    for root, dirs, files in os.walk(songs_directory):
        for file in files:
            if not file.endswith(".osu"):
                continue

            file_path = os.path.join(root, file)

            try:
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    content = f.read()

                title_match = re.search(r"^Title:(.*)$", content, re.MULTILINE)
                version_match = re.search(r"^Version:(.*)$", content, re.MULTILINE)

                if not title_match:
                    continue

                title = title_match.group(1).strip()

                if title.lower() != beatmap_name.lower():
                    continue

                version = version_match.group(1).strip() if version_match else ""

                if difficulty_name and version.lower() == difficulty_name.lower():
                    return file_path

                title_matches.append(file_path)

            except (OSError, UnicodeDecodeError):
                continue

    if len(title_matches) == 1:
        return title_matches[0]

    if title_matches:
        return title_matches[0]

    for root, dirs, files in os.walk(songs_directory):
        for file in files:
            if file.endswith(".osu") and beatmap_name.lower() in file.lower():
                return os.path.join(root, file)

    return None


def parse_hit_object_simple(line):
    parts = line.rstrip("\r\n").split(",")

    if len(parts) < 5:
        return None

    try:
        x = int(parts[0])
        y = int(parts[1])
        time = int(parts[2])
    except ValueError:
        return None

    return {
        "x": x,
        "y": y,
        "time": time
    }


def compute_most_common_space(objects):
    spaces = {}

    for i in range(len(objects) - 1):
        space = objects[i + 1]["time"] - objects[i]["time"]

        if space == 0:
            continue

        spaces[space] = spaces.get(space, 0) + 1

    if not spaces:
        return None

    return max(spaces.items(), key=lambda item: item[1])[0]


def create_inverse_hit_objects(hit_object_lines):
    objects = []

    for line in hit_object_lines:
        obj = parse_hit_object_simple(line)

        if obj is not None:
            objects.append(obj)

    if not objects:
        return []

    objects.sort(key=lambda obj: obj["time"])

    most_common_space = compute_most_common_space(objects)
    output_lines = []

    for index, obj in enumerate(objects):
        next_same_column_time = 0

        for later in objects[index + 1:]:
            if later["x"] == obj["x"]:
                next_same_column_time = later["time"]
                break

        illegal_ln = True

        if next_same_column_time != 0 and most_common_space is not None:
            release_gap = math.floor(
                most_common_space * RELEASE_DIVISOR
            )

            min_gap = most_common_space * MIN_DIVISOR

            illegal_ln = (
                next_same_column_time - release_gap
            ) <= (
                obj["time"] + min_gap
            )

        if next_same_column_time == 0 or illegal_ln:
            note_type = 1
            end_field = 0
        else:
            note_type = 128
            end_field = (
                next_same_column_time
                - math.floor(
                    most_common_space * RELEASE_DIVISOR
                )
            )

        line = (
            f"{obj['x']},{obj['y']},{obj['time']},{note_type},0,"
            f"{end_field}:0:0:0:0:\n"
        )

        output_lines.append(line)

    return output_lines


def edit_osu_file(original_path):
    with open(original_path, "r", encoding="utf-8-sig") as file:
        lines = file.readlines()

    metadata_section = False
    hit_objects_section = False
    new_lines = []
    hit_object_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped == "[Metadata]":
            metadata_section = True
            hit_objects_section = False
            new_lines.append(line)
            continue

        if stripped == "[HitObjects]":
            metadata_section = False
            hit_objects_section = True
            new_lines.append(line)
            continue

        if line.startswith("[") and (
            metadata_section or hit_objects_section
        ):
            metadata_section = False
            hit_objects_section = False
            new_lines.append(line)
            continue

        if metadata_section and line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()

            if not version.lower().endswith("(inverse)"):
                line = f"Version: {version} (inverse)\n"

            new_lines.append(line)
            continue

        if hit_objects_section:
            hit_object_lines.append(line)
            continue

        new_lines.append(line)

    inverse_hit_objects = create_inverse_hit_objects(
        hit_object_lines
    )

    new_lines.extend(inverse_hit_objects)

    with open(original_path, "w", encoding="utf-8") as file:
        file.writelines(new_lines)

    return original_path


def main():
    osu_title = find_osu_window_title()

    if not osu_title:
        return

    beatmap_name = extract_beatmap_name(osu_title)
    difficulty_name = extract_difficulty_name(osu_title)

    if not beatmap_name:
        return

    osu_file_path = find_osu_file_path(
        beatmap_name,
        difficulty_name,
        SONGS_DIRECTORY
    )

    if not osu_file_path:
        return

    edit_osu_file(osu_file_path)


if __name__ == "__main__":
    main()