import traceback
from flask import Markup
import re

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'srt'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def output_html(pros, voc, definition, word_ex_list):
    last = len(word_ex_list)
    count = 0
    ex_list = list()
    for word, ex in word_ex_list:
        count += 1
        # s = "[^a-zA-Z]" + word + "[^a-zA-z]"
        # word = re.sub(s, '<b>' + word + '<b>', word)
        i = re.search("(.*)" + word + "([^a-zA-Z].*)", ex)
        try:
            first_part = i.group(1)
            second_part = i.group(2)
            ex_list.append(first_part + '<b>' + word + '</b>' + second_part)
            if count != last:
                ex_list.append('<br><br>')
        except:
            # TODO check manipulator bug
            print(traceback.format_exc())
            print word
            print ex
    return voc, Markup('<input type="checkbox" name="' + voc + '" value="' + pros + '"></input>'), \
           pros, definition, Markup(''.join(ex_list))
