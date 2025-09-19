#!/usr/bin/python3

"""Convert DHV A-Schein paragliding test PDFs to a tab-separated text file.

See README.adoc for more details.

Copyright (c) 2020, 2025 Pontus Lurcock
Released under the MIT License; see the accompanying LICENSE.txt file.
"""


import argparse
import subprocess
import tempfile
import os
import re
import sys
from typing import Tuple, List, Union, Mapping
from enum import Enum
import csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("questions_pdf")
    parser.add_argument(
        "pictures_pdf", help='Use "-" if no pictures are to be processed'
    )
    parser.add_argument(
        "pictures_output_dir",
        help='Use "-" if no pictures are to be processed',
    )
    parser.add_argument("output_tsv")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp_dir:
        matrix = process_files(
            args.questions_pdf,
            args.pictures_pdf,
            args.pictures_output_dir,
            temp_dir,
        )
    with open(args.output_tsv, "w") as fh:
        writer = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_ALL)
        for row in matrix:
            writer.writerow(row)


def process_files(questions_compressed, pictures_pdf, pictures_dir, temp_dir):
    questions_file = os.path.join(temp_dir, "questions.pdf")
    decompress_questions_pdf(questions_compressed, questions_file)
    correct_answers = construct_correct_answer_list(questions_file)
    question_list = parse_text_from_pdf(questions_compressed, temp_dir)
    if pictures_pdf != "-":
        image_numbers = extract_image_numbers(pictures_pdf, temp_dir)
        filetype_map = extract_images(
            pictures_pdf, pictures_dir, image_numbers
        )
    else:
        filetype_map = {}
    return create_output_matrix(question_list, correct_answers, filetype_map)


def decompress_questions_pdf(source: str, destination: str) -> None:
    cmd = [
        "qpdf",
        "--decode-level=all",
        "--compress-streams=n",
        source,
        destination,
    ]
    result = subprocess.run(cmd, stdout=sys.stdout)
    if result.returncode not in [0, 3]:
        raise subprocess.CalledProcessError(result.returncode, cmd)


def construct_correct_answer_list(questions_file: str) -> List[int]:
    # Mapping quadruplets of right/wrong answers like this gives us built-in
    # sanity checking: we'll get an exception for any quadruplet that doesn't
    # contain exactly one correct answer.
    answer_map = dict(BSSS=0, SBSS=1, SSBS=2, SSSB=3)
    answer_list = []
    with open(questions_file, "r", encoding="iso-8859-1") as fh:
        answer_group = ""
        for line in fh.readlines():
            # Match an empty box S (wrong answer) or filled box B (correct
            # answer)
            match = re.match(
                r"42\.52 \d+\.\d+ 8\.50 -8\.50 re ([BS])", line.strip()
            )
            if match:
                answer_group += match.group(1)
            if len(answer_group) == 4:
                answer_list.append(answer_map[answer_group])
                answer_group = ""
    return answer_list


def parse_text_from_pdf(
    questions_pdf: str, temp_dir: str
) -> List[Tuple[Union[str, int], ...]]:
    questions_textfile = os.path.join(temp_dir, "questions.txt")
    subprocess.run(
        ["pdftotext", "-layout", questions_pdf, questions_textfile], check=True
    )
    with open(questions_textfile, "r") as fh:
        lines = fh.readlines()

    class State(Enum):
        ignore = 0  # between questions
        question = 1
        answer_a = 2
        answer_b = 3
        answer_c = 4
        answer_d = 5

    current_section = 1
    last_question_number = 0
    state = State.ignore
    current_q = []
    question_list = []

    for line_raw in lines:
        line = re.sub(" +", " ", line_raw.strip())
        if state == State.ignore:
            match = re.match(r"^(\d+)\) (.*)$", line)
            if match:
                # start of question
                assert len(current_q) == 0
                q_number = int(match.group(1))
                if q_number < last_question_number:
                    current_section += 1
                q_text = match.group(2)
                q_match = re.match(r"^Abbildung (\d+): *(.*)$", q_text)
                if q_match:
                    img_number = int(q_match.group(1))
                    q_text = q_match.group(2)
                else:
                    img_number = 0

                current_q.append(
                    "%d.%d. %s" % (current_section, q_number, q_text)
                )
                current_q.append(img_number)
                state = State.question
                last_question_number = q_number
        elif state == state.question:
            assert len(current_q) == 2
            match = re.match(r"^A\) *(.*)$", line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_a
            else:
                current_q[0] += " " + line
        elif state == state.answer_a:
            assert len(current_q) == 3
            match = re.match(r"^B\) *(.*)$", line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_b
            else:
                current_q[2] += " " + line
        elif state == state.answer_b:
            assert len(current_q) == 4
            match = re.match(r"^C\) *(.*)$", line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_c
            else:
                current_q[3] += " " + line
        elif state == state.answer_c:
            assert len(current_q) == 5
            match = re.match(r"^D\) *(.*)$", line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_d
            else:
                current_q[4] += " " + line
        elif state == state.answer_d:
            assert len(current_q) == 6
            if line == "":
                state = State.ignore
                question_list.append(tuple(current_q))
                current_q = []
            else:
                current_q[5] += " " + line

    return question_list


def create_output_matrix(
    question_list: List[Tuple[Union[str, int], ...]],
    correct_answers: List[int],
    filetype_map: Mapping[int, str],
) -> List[List[str]]:
    assert len(question_list) == len(correct_answers)

    def escape(string):
        # Occasionally there's a lurking pre-escaped quotation mark,
        # so we remove any existing backslashes first.
        return string.replace("\\", "").replace('"', r"\"")

    result = []
    for i in range(len(question_list)):
        question, img_number, ans_a, ans_b, ans_c, ans_d = question_list[i]
        correct_index = correct_answers[i]
        answers = [ans_a, ans_b, ans_c, ans_d]
        correct_answer = answers.pop(correct_index)
        if img_number != 0:
            img_html = '<img src="%s.%s" alt="Abbildung %d"><br>' % (
                make_image_name(img_number),
                filetype_map[img_number],
                img_number,
            )
            question = img_html + escape(question)
        result.append(
            [question, escape(correct_answer)] + list(map(escape, answers))
        )
    return result


def extract_image_numbers(images_filename: str, temp_dir: str) -> List[int]:
    text_filename = os.path.join(temp_dir, "images.txt")
    subprocess.run(["pdftotext", images_filename, text_filename], check=True)
    with open(text_filename, "r") as fh:
        lines = fh.readlines()
    result = []
    for line in lines:
        match = re.match(r"^Abbildung (\d+)", line.strip())
        if match:
            result.append(int(match.group(1)))
    return result


def extract_images(
    images_pdf: str, images_dir: str, image_numbers: List[int]
) -> Mapping[int, str]:
    # Empty the directory of any existing files
    for root, dirs, files in os.walk(images_dir):
        for f in files:
            os.unlink(os.path.join(root, f))

    subprocess.run(
        ["pdfimages", "-all", images_pdf, os.path.join(images_dir, "x")]
    )

    filetype_map = {}
    image_index = 0
    for filename in sorted(os.listdir(images_dir)):
        path = os.path.join(images_dir, filename)
        stat = os.stat(path)
        if filename in ["x-089.png", "x-105.png"] or stat.st_size in [
            78247,
            25220,
        ]:
            # Discard unwanted images.
            # The PNGs in the headers have one of two known sizes.
            # Numbers 089 and 105 are blank.
            os.unlink(path)
        else:
            match = re.search(r"\.(...)$", filename)
            image_number = image_numbers[image_index]
            suffix = match.group(1)

            dest = os.path.join(
                images_dir, make_image_name(image_numbers[image_index])
            )
            if suffix == "tif":
                # AnkiDroid apparently can't handle TIFFs, so we convert them
                # to a supported format. The two TIFFs in this collection are
                # photographs, so JPEG is a reasonable choice.
                subprocess.run(
                    ["gm", "convert", path, "-quality", "90", dest + ".jpg"],
                    check=True,
                )
                os.unlink(path)
                filetype_map[image_number] = "jpg"
            else:
                os.rename(path, dest + "." + suffix)
                filetype_map[image_number] = suffix
            image_index += 1

    return filetype_map


def make_image_name(image_number: int) -> str:
    return "DHV-Fragen-Abbildung-%03d" % image_number


if __name__ == "__main__":
    main()
