#!/usr/bin/python3

import argparse
import subprocess
import tempfile
import os
import re
import sys
from typing import Tuple, List
from enum import Enum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('questions_pdf')
    parser.add_argument('pictures_pdf')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp_dir:
        process_files(args.questions_pdf, args.pictures_pdf, temp_dir)


def process_files(questions_compressed, pictures_pdf, temp_dir):
    questions_file = os.path.join(temp_dir, 'questions.pdf')
    decompress_questions_pdf(questions_compressed, questions_file)
    correct_answers = construct_correct_answer_list(questions_file)
    question_list = parse_text_from_pdf(questions_compressed, temp_dir)
    for line in question_list:
        print(line)


def decompress_questions_pdf(source, destination):
    cmd = ['qpdf', '--decode-level=all', '--compress-streams=n',
           source, destination]
    result = subprocess.run(cmd, stdout=sys.stdout)
    if result.returncode not in [0, 3]:
        raise subprocess.CalledProcessError(result.returncode, cmd)


def construct_correct_answer_list(questions_file):
    # Mapping quadruplets of right/wrong answers like this gives us built-in
    # sanity checking: we'll get an exception for any quadruplet that doesn't
    # contain exactly one correct answer.
    answer_map = dict(BSSS=0, SBSS=1, SSBS=2, SSSB=3)
    answer_list = []
    with open(questions_file, 'r', encoding='iso-8859-1') as fh:
        answer_group = ''
        for line in fh.readlines():
            # Match an empty box (wrong answer) or filled box (correct
            # answer)
            match = re.match(r'42\.52 \d+\.\d+ 8\.50 -8\.50 re ([BS])',
                             line.strip())
            if match:
                answer_group += match.group(1)
            if len(answer_group) == 4:
                answer_list.append(answer_map[answer_group])
                answer_group = ''
    return answer_list


def parse_text_from_pdf(questions_pdf: str, temp_dir: str) -> \
        List[Tuple[str, ...]]:
    questions_textfile = os.path.join(temp_dir, 'questions.txt')
    subprocess.run(['pdftotext', '-layout', questions_pdf,
                    questions_textfile], check=True)
    with open(questions_textfile, 'r') as fh:
        lines = fh.readlines()

    class State(Enum):
        ignore = 0  # between questions
        question = 1
        answer_a = 2
        answer_b = 3
        answer_c = 4
        answer_d = 5

    # TODO: handle question numbers properly
    # Parse the question number and increment the section if the question
    # number has reset to 1.
    section = 0
    state = State.ignore
    current_q = []
    question_list = []

    for line_raw in lines:
        line = re.sub(' +', ' ', line_raw.strip())
        if state == State.ignore:
            if re.match(r'^\d+\) ', line):
                # start of question
                assert(len(current_q) == 0)
                current_q.append(line)
                state = State.question
        elif state == state.question:
            assert (len(current_q) == 1)
            if re.match(r'^A\) ', line):
                current_q.append(line)
                state = State.answer_a
            else:
                current_q[0] += (' ' + line)
        elif state == state.answer_a:
            assert (len(current_q) == 2)
            if re.match(r'^B\) ', line):
                current_q.append(line)
                state = State.answer_b
            else:
                current_q[1] += (' ' + line)
        elif state == state.answer_b:
            assert (len(current_q) == 3)
            if re.match(r'^C\) ', line):
                current_q.append(line)
                state = State.answer_c
            else:
                current_q[2] += (' ' + line)
        elif state == state.answer_c:
            assert (len(current_q) == 4)
            if re.match(r'^D\) ', line):
                current_q.append(line)
                state = State.answer_d
            else:
                current_q[3] += (' ' + line)
        elif state == state.answer_d:
            assert (len(current_q) == 5)
            if line == '':
                state = State.ignore
                question_list.append(tuple(current_q))
                current_q = []
            else:
                current_q[4] += (' ' + line)

    return question_list


if __name__ == '__main__':
    main()
