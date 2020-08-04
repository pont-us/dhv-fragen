#!/usr/bin/python3

import argparse
import subprocess
import tempfile
import os
import re
import sys
from typing import Tuple, List, Union
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
    output_matrix = create_output_matrix(question_list, correct_answers)
    for line in output_matrix:
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
        List[Tuple[Union[str, int], ...]]:
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
    current_section = 1
    last_question_number = 0
    state = State.ignore
    current_q = []
    question_list = []

    for line_raw in lines:
        line = re.sub(' +', ' ', line_raw.strip())
        if state == State.ignore:
            match = re.match(r'^(\d+)\) (.*)$', line)
            if match:
                # start of question
                assert(len(current_q) == 0)
                q_number = int(match.group(1))
                if q_number < last_question_number:
                    current_section += 1
                q_text = match.group(2)
                q_match = re.match(r'^Abbildung (\d+): *(.*)$', q_text)
                if q_match:
                    img_number = int(q_match.group(1))
                    q_text = q_match.group(2)
                else:
                    img_number = 0

                current_q.append('%d.%d. %s' %
                                 (current_section, q_number, q_text))
                current_q.append(img_number)
                state = State.question
                last_question_number = q_number
        elif state == state.question:
            assert (len(current_q) == 2)
            match = re.match(r'^A\) *(.*)$', line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_a
            else:
                current_q[0] += (' ' + line)
        elif state == state.answer_a:
            assert (len(current_q) == 3)
            match = re.match(r'^B\) *(.*)$', line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_b
            else:
                current_q[2] += (' ' + line)
        elif state == state.answer_b:
            assert (len(current_q) == 4)
            match = re.match(r'^C\) *(.*)$', line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_c
            else:
                current_q[3] += (' ' + line)
        elif state == state.answer_c:
            assert (len(current_q) == 5)
            match = re.match(r'^D\) *(.*)$', line)
            if match:
                current_q.append(match.group(1))
                state = State.answer_d
            else:
                current_q[4] += (' ' + line)
        elif state == state.answer_d:
            assert (len(current_q) == 6)
            if line == '':
                state = State.ignore
                question_list.append(tuple(current_q))
                current_q = []
            else:
                current_q[5] += (' ' + line)

    return question_list


def create_output_matrix(question_list, correct_answers):
    assert(len(question_list) == len(correct_answers))
    result = []
    for i in range(len(question_list)):
        question, img_number, ans_a, ans_b, ans_c, ans_d = question_list[i]
        correct_index = correct_answers[i]
        answers = [ans_a, ans_b, ans_c, ans_d]
        correct_answer = answers.pop(correct_index)
        if img_number != 0:
            # TODO: add the correct image suffix
            # We'll need the directory of extracted images to do this.
            img_html = '<img src="%s" alt="Abbildung %d"><br>' % \
                       (make_image_name(img_number), img_number)
            question = img_html + question
        result.append([question, correct_answer] + answers)
    return result


def make_image_name(image_number):
    return 'DHV-Fragen-Abbildung-%03d' % image_number


if __name__ == '__main__':
    main()
