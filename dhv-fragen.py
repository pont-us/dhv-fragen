#!/usr/bin/python3

import argparse
import subprocess
import tempfile
import os
import re
import sys


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


if __name__ == '__main__':
    main()
