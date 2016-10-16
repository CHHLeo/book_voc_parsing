import re
import sqlite3
import collections
import nltk
from nltk.stem.wordnet import WordNetLemmatizer
from nltk.corpus import wordnet as wn
from sqlalchemy.sql import text
import os

# nltk.download()
dir_path = os.path.dirname(os.path.realpath(__file__))
# nltk.data.path.append(dir_path + "\\lib\\nltk_data")
nltk.data.path.append("C:\Users\Owner\AppData\Roaming\\nltk_data")
lmtzr = WordNetLemmatizer()


def is_search_voc(voc, pros, db, app, value):
    filter = "AND remember = 0"
    # cur_big.execute('SELECT phonetic, definition FROM big_capital WHERE voc = "' + voc + '"' + filter)
    # cur_big_list = cur_big.fetchall()
    # if cur_big_list:
    #     return [False, cur_big_list]
    if value == '_Collins':
        cur_list = db.engine.execute(text('SELECT phonetic, definition FROM '
                                                                   'vocabulary WHERE lower(voc)= "' +
                                                                   voc.lower() + '"' + filter))
        cur_list = list(cur_list)
        if cur_list:
            return [True, cur_list]
    else:
        cur_list = db.engine.execute(text('SELECT phonetic,definition FROM '
                                                                'AmericanYouDao WHERE lower(voc) ="' +
                                                                voc.lower() + '" AND pos = "' + pros + '"' +
                                                                filter))
        cur_list = list(cur_list)
        if cur_list:
            return [True, cur_list]

    return [False, ]


def get_example(all_voc, ex_length, index):
    if index < ex_length:
        ex = all_voc[:index] + all_voc[index:index + ex_length]
    elif index > (len(all_voc) - ex_length):
        ex = all_voc[index - ex_length:index] + all_voc[index:]
    else:
        ex = all_voc[index - ex_length:index + ex_length]
    return ex


def change_index(all_voc, all_ex, ex_length):
    for voc, index_list in all_ex.items():
        ex_list = list()
        for index in index_list:
            ex_list.append(' '.join(get_example(all_voc, ex_length, index)))
        all_ex[voc] = ex_list
    return all_ex


sent_detector = nltk.data.load('tokenizers/punkt/english.pickle')
tagger = nltk.data.load('taggers/maxent_treebank_pos_tagger/english.pickle')


def _morphy(word, pos):
    exceptions = wn._exception_map[pos]
    if word in exceptions:
        return exceptions[word]


def content_handle(content, db, app, value, specific_voc_pos=None):
    all_ex = collections.OrderedDict()
    wanted_voc = dict()
    content = re.sub(u'[^\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\u10000-\u10FFFF]+', '', content).decode(
            'utf8').strip()

    sents = sent_detector.tokenize(content)
    max_ex_length = 80
    max_ex_num = 3
    for sent in sents:
        tagged_tokens = tagger.tag(nltk.word_tokenize(sent))
        count = 0
        last = len(tagged_tokens)
        ex = sent.replace('\n', ' ')
        ex_word_len = len(tagged_tokens)
        for word, pros in tagged_tokens:
            if not re.search('[a-zA-Z]+', word):
                continue
            count += 1
            if count == 1:
                word_z = word[0].lower() + word[1:]
            elif count == last and word[-1] == '.':
                word_z = word[:-1]
            else:
                word_z = word

            if re.match('N', pros):
                mor_voc = _morphy(word_z, 'n')
                if not mor_voc:
                    voc = lmtzr.lemmatize(word_z)
                else:
                    if len(mor_voc) > 1:
                        print mor_voc, word_z
                    voc = mor_voc[0]
            elif re.match('V', pros):
                mor_voc = _morphy(word_z, 'v')
                if not mor_voc:
                    voc = lmtzr.lemmatize(word_z, 'v')
                else:
                    if len(mor_voc) > 1:
                        print mor_voc, word_z
                    voc = mor_voc[0]
            else:
                voc = word_z

            if specific_voc_pos:
                try:
                    for v, p in specific_voc_pos:
                        if (p and (v, p[0]) == (voc, pros[0])) or (not p and v == voc):
                            raise TypeError
                    continue
                except TypeError:
                    pass

            if (voc, pros) not in wanted_voc:
                wanted_voc[voc, pros] = is_search_voc(voc, pros[0], db, app, value)
            if wanted_voc[voc, pros][0] and ex_word_len < max_ex_length:
                if (voc, pros) not in all_ex:
                    all_ex[voc, pros] = [(word, ex)]
                elif ex not in (i[1] for i in all_ex[voc, pros]) and len(all_ex[voc, pros]) < max_ex_num:
                    all_ex[voc, pros].append((word, ex))

    return all_ex, wanted_voc


def srt_content_handle(content):
    pattern_subtitle = re.compile("(?<=,[0-9]{3}\n)[\d\D]*?(?=\n\n)")
    ex_str = re.findall(pattern_subtitle, content)
    for i in range(len(ex_str)):
        if re.match("[a-zA-Z]", ex_str[i][-1]):
            ex_str[i] += "."
    return ' '.join(ex_str)

##################### file content #################################
# file_name = 'Vanilla_sky'
# file_name = 'A Girls Guide To 21st Century Sex1'
# out_name = file_name + '_1'
# file_type = 'srt'
# f = open(file_name + '.' + file_type, 'r')
# content = f.read()
# f.close()
# print srt_content_handle(content)
# # content_handle(srt_content_handle(content))
# print srt_content_handle(content)[26800:26805]
###################################################################
###################################################################
# file_name = 'input_file/growth hacker'
# out_name = file_name + "_1204_x"
# content = pdf_miner.convert(file_name+'.pdf')
# content_handle(content,db)
###################################################################
###################################################################
# pdfFileObj = open(file_name + '.pdf', 'rb')
# pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
#
# text_list = list()
# for Page in range(pdfReader.numPages):
#     text = pdfReader.getPage(Page).extractText()
#     print text
    # text_list.append(text)
    #     print text
# content_handle(' '.join(text_list), ex_length)
# pdfFileObj.close()
#
########################### file content ######################
