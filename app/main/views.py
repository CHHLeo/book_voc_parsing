import threading

import time
import traceback
from glob import glob

from flask import render_template, session, redirect, url_for, current_app, jsonify, g, Response, make_response, \
    copy_current_request_context
from .. import db
from ..models import Collins, Coca
from ..email import send_email
from . import main
from .forms import NameForm
from flask import request
import re
from sqlalchemy.sql import text
import cPickle as pickle
from os import listdir
from .. import pdf_miner
from .. import file_read_output_docx
from .. import utils
import os
from flask_paginate import Pagination
from multiprocessing.pool import Pool
from pyPdf import PdfFileReader
import json

dir_path = os.path.dirname(os.path.realpath(__file__))
UPLOAD_FOLDER = os.path.join(dir_path, '../upload')

upload_lock_collins = threading.Lock()
upload_lock_coca = threading.Lock()

page_splice = 10


# i TODO add cover: use carousel
@main.route('/', methods=['GET', 'POST'])
def index():
    form = NameForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.name.data).first()
        if user is None:
            user = User(username=form.name.data)
            db.session.add(user)
            session['known'] = False
            if current_app.config['FLASKY_ADMIN']:
                send_email(current_app.config['FLASKY_ADMIN'], 'New User',
                           'mail/new_user', user=user)
        else:
            session['known'] = True
        session['name'] = form.name.data
        return redirect(url_for('.index'))
    return render_template('index.html',
                           form=form, name=session.get('name'),
                           known=session.get('known', False))


@main.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        for file in request.files.getlist('my_file'):
            for f in os.listdir(UPLOAD_FOLDER):
                if f == file.filename:
                    continue
            if file and utils.allowed_file(file.filename):
                file.save(os.path.join(UPLOAD_FOLDER, file.filename))

                # KP: thread counting cool
                @copy_current_request_context
                def thread_background_voc(book, value, k, upload_lock):
                    content = pdf_miner.convert(file_name, [k * page_inter + 1, (k + 1) * page_inter])
                    all_ex, wanted_voc = file_read_output_docx.content_handle(content, db, current_app, value)
                    upload_lock.acquire()
                    if os.path.isfile(book + value + '_up_.pk'):
                        with open(book + value + '_up_.pk', 'rb') as input:
                            pre_all_ex = pickle.load(input)
                            pre_wanted_voc = pickle.load(input)
                            count = pickle.load(input)
                            count.append(k)
                            for i in all_ex:
                                for j in pre_all_ex:
                                    if i == j:
                                        for g in all_ex[i]:
                                            if g not in pre_all_ex[j]:
                                                pre_all_ex[j].append(g)
                                        break
                                else:
                                    pre_all_ex[i] = all_ex[i]
                            pre_wanted_voc.update(wanted_voc)
                            all_ex = pre_all_ex
                            wanted_voc = pre_wanted_voc
                        with open(book + value + '_up_.pk', 'wb') as output:
                            if len(count) == kk:
                                count = []
                                with open(book + value + '.pk', 'wb') as out:
                                    pickle.dump(all_ex, out, -1)
                                    pickle.dump(wanted_voc, out, -1)
                            pickle.dump(all_ex, output, -1)
                            pickle.dump(wanted_voc, output, -1)
                            pickle.dump(count, output, -1)
                    else:
                        with open(book + value + '_up_.pk', 'wb') as output:
                            pickle.dump(all_ex, output, -1)
                            pickle.dump(wanted_voc, output, -1)
                            pickle.dump([k], output, -1)
                    upload_lock.release()

                book = file.filename
                file_name = UPLOAD_FOLDER + '/' + book
                pdf = PdfFileReader(open(file_name, 'rb'))
                pages = pdf.getNumPages()
                page_inter = pages / page_splice
                if not page_inter:
                    page_inter = 1
                kk = 0
                while True:
                    if kk * page_inter + 1 >= pages:
                        break
                    kk += 1

                # KP: thread calculation
                for i in range(kk):
                    global upload_lock_collins
                    threading.Thread(target=thread_background_voc,
                                     args=(book, '_Collins', i, upload_lock_collins)).start()
                    global upload_lock_coca
                    threading.Thread(target=thread_background_voc,
                                     args=(book, '_Coca', i, upload_lock_coca)).start()
        for i in request.form:
            print UPLOAD_FOLDER + '/' + i
            os.remove(UPLOAD_FOLDER + '/' + i)
            for file in os.listdir(dir_path + '/../../'):
                if file.startswith(i):
                    os.remove(os.path.join(dir_path + '/../../', file))
        return redirect(url_for('.book'))
    books_list = listdir(UPLOAD_FOLDER)
    # KP: sort by data time: cool
    books_list.sort(key=lambda x: os.stat(os.path.join(UPLOAD_FOLDER, x)).st_mtime)
    return render_template('book.html', books_list=books_list)


@main.route('/dic', methods=['GET'])
def dic():
    return render_template('dic.html')


@main.route('/dic/?data=<data>', methods=['POST', 'GET'])
def voc_database(data, voc=''):
    varkey = request.form.keys()
    page = request.args.get('page', 1, type=int)
    showall = request.args.get('showall')
    print varkey

    if 'b_search' in varkey:
        voc = request.form['xsearchx']
        # KP: use redirect to make post to get(resolve nested form issue)
        return redirect(url_for('.voc_database', data=data, showall=True, voc=voc))
    if 'b_all' in varkey:
        return redirect(url_for('.voc_database', data=data))

    page_number = 50
    rem = '1' if data[-1] == 'r' else '0'
    if request.method == 'POST':
        update_wanted_dic(str(int(not int(rem))))
        return redirect(url_for('.voc_database', data=data))

    if re.match('Collins', data):
        if showall:
            voc = request.args.get('voc')
            pagination = Collins.query.filter(Collins.remember == rem, Collins.voc.like(voc + '%')).paginate(page,
                                                                                                             per_page=page_number,
                                                                                                             error_out=False)
        else:
            pagination = Collins.query.filter(Collins.remember == rem).paginate(page,
                                                                                per_page=page_number,
                                                                                error_out=False)

        datas = pagination.items
    elif re.match('Coca', data):
        if showall:
            voc = request.args.get('voc')
            pagination = Coca.query.filter(Coca.remember == rem, Coca.voc.like(voc + '%'),
                                           Coca.rank < 20000).paginate(page, per_page=page_number, error_out=False)
        else:
            pagination = Coca.query.filter(Coca.remember == rem, Coca.rank < 20000).order_by(Coca.rank).paginate(page,
                                                                                                                 per_page=page_number,
                                                                                                                 error_out=False)
        datas = pagination.items

    return render_template('data.html', DBdata=data,
                           datas=(zip(range((page - 1) * page_number, page * page_number), list(datas))),
                           pagination=pagination, showall=showall, voc=voc)


@main.route('/thread_book_voc_total/?book=<book>&value=<value>', methods=['GET'])
def thread_book_voc_total(value, book):
    if os.path.isfile(book + value + '.pk'):
        with open(book + value + '.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)
    elif os.path.isfile(book + value + '_up_.pk'):
        with open(book + value + '_up_.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)
    else:
        return jsonify(vocs='xxx')

    vocs = list()
    for (voc_pros, word_ex_list) in (all_ex.items()):
        vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                      word_ex_list))
    return jsonify(vocs=vocs)


@main.route('/instant_voc/?book=<book>&value=<value>', methods=['GET'])
@main.route('/instant_voc/?book=<book>&value=<value>&voc=<voc>', methods=['GET'])
def instant_voc(value, book, voc='', all=''):
    voc = str(voc)
    if os.path.isfile(book + value + '.pk'):
        with open(book + value + '.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)
    else:
        return jsonify(vocs='xxx')

    if voc != '':
        for i in all_ex:
            if not re.match(voc, i[0]):
                all_ex.pop(i)
    else:
        all = 'xxx'

    vocs = list()
    for (voc_pros, word_ex_list) in (all_ex.items()):
        vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                      word_ex_list))
    return jsonify(vocs=vocs, all=all)


@main.route('/check_file_exist/?book=<book>%value=<value>', methods=['GET'])
def check_file_exist(book, value):
    while True:
        if os.path.isfile(book + value + '.pk'):
            return jsonify()


@main.route('/check_up/?book=<book>&value=<value>&_cached_stamp=<cs>', methods=['GET'])
def check_up(book, value, cs=0):
    filename = book + value + '_up_.pk'
    while True:
        if os.path.isfile(filename):
            stamp = os.stat(filename).st_mtime
            cs = float(cs)
            if stamp != cs:
                cs = stamp
                if value == '_Collins':
                    global upload_lock_collins
                    lock = upload_lock_collins
                else:
                    global upload_lock_coca
                    lock = upload_lock_coca

                lock.acquire()
                with open(filename, 'rb') as input:
                    all_ex = pickle.load(input)
                    wanted_voc = pickle.load(input)
                lock.release()
                # TODO decrease duplicate code
                vocs = list()
                for (voc_pros, word_ex_list) in (all_ex.items()):
                    vocs.append(
                            utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                              word_ex_list))
                return jsonify(cs=cs, vocs=vocs)


@main.route('/book_voc/<book>?value=<value>', methods=['POST', 'GET'])
@main.route('/book_voc/<book>?value=<value>?k=<k>', methods=['POST', 'GET'])
@main.route('/book_voc/<book>?value=<value>', methods=['POST', 'GET'])
@main.route('/book_voc/<book>?value=<value>?k=<k>', methods=['POST', 'GET'])
def book_voc(book, value, k=0):
    # TODO set pythonanywhere mysql
    if request.method == 'POST':
        update_wanted_dic()
        return redirect(url_for('.book_voc', book=book, value=value))

    file_name = UPLOAD_FOLDER + '/' + book
    pdf = PdfFileReader(open(file_name, 'rb'))
    pages = pdf.getNumPages()
    # TODO bug when pages few -> test
    page_inter = pages / page_splice
    if not page_inter:
        page_inter = 1
    vocs = list()

    if os.path.isfile(book + value + '.pk'):
        # check pk already prepared or not
        with open(book + value + '.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)

            for (voc_pros, word_ex_list) in (all_ex.items()):
                # TODO a bug for wanted_voc false? continuely watch
                vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                              word_ex_list))
            return render_template('book_voc.html', vocs=vocs, book=book, value=value)

    elif os.path.isfile(book + value + '_up_.pk'):
        # check _up_pk already prepared or not
        if value == '_Collins':
            global upload_lock_collins
            lock = upload_lock_collins
        else:
            global upload_lock_coca
            lock = upload_lock_coca
        lock.acquire()
        with open(book + value + '_up_.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)
        lock.release()
        for (voc_pros, word_ex_list) in (all_ex.items()):
            vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                          word_ex_list))
        return render_template('book_voc.html', page_inter=page_inter, vocs=vocs, book=book, value=value,
                               pages=pages)
    else:
        return render_template('book_voc.html', page_inter=page_inter, vocs=vocs, book=book, value=value,
                               pages=pages)


@main.route('/test/<tt>')
def test(tt):
    return jsonify(a="a")


@main.route('/test2/')
def test2():
    return render_template('test.html', kk='k')


# @main.route('/thread_book_voc/?value=<value>&book=<book>&page_inter=<page_inter>&k=<k>&pages=<pages>')
# def thread_book_voc(value, book, page_inter, k, pages):
#     file_name = UPLOAD_FOLDER + '/' + book
#     k = int(k)
#     pages = int(pages)
#     page_inter = int(page_inter)
#     print k
#     content = pdf_miner.convert(file_name, [k * page_inter + 1, (k + 1) * page_inter])
#     all_ex, wanted_voc = file_read_output_docx.content_handle(content, db, current_app, value)
#     vocs = list()
#     for (voc_pros, word_ex_list) in (all_ex.items()):
#         vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
#                                       word_ex_list))
#     threading.Thread(target=book_voc_process, args=(book, value, all_ex, wanted_voc)).start()
#
#     return jsonify(vocs=vocs)
#
#
# def book_voc_process(book, value, all_ex, wanted_voc):
#     try:
#         # TODO bug when middle delete pk (it will be fix when change to append dic)
#         global book_voc_lock
#         book_voc_lock.acquire()
#         with open(book + value + '_pre_.pk', 'rb') as input:
#             pre_all_ex = pickle.load(input)
#             pre_wanted_voc = pickle.load(input)
#             for i in all_ex:
#                 for j in pre_all_ex:
#                     if i == j:
#                         for g in all_ex[i]:
#                             if g not in pre_all_ex[j]:
#                                 pre_all_ex[j].append(g)
#                         break
#                 else:
#                     pre_all_ex[i] = all_ex[i]
#             pre_wanted_voc.update(wanted_voc)
#             all_ex = pre_all_ex
#             wanted_voc = pre_wanted_voc
#         with open(book + value + '_pre_.pk', 'wb') as output:
#             pickle.dump(all_ex, output, -1)
#             pickle.dump(wanted_voc, output, -1)
#         book_voc_lock.release()
#     except Exception as e:
#         # print e
#         # print traceback.print_exc()
#         book_voc_lock.release()



def update_wanted_dic(remember="1"):
    for i in request.form:
        for j in request.form:
            print j, request.form[j]
        voc = i
        if voc == 'xsearchx':
            continue
        pos = request.form[i]
        db.engine.execute(
                text('UPDATE vocabulary SET remember = "' + remember + '" WHERE lower(voc) = "' + voc.lower() + '"'))
        if pos != 'on' and pos != '':
            db.engine.execute(text(
                    'UPDATE AmericanYouDao SET remember = "' + remember + '" WHERE lower(voc) = "' + voc.lower() + '" AND pos = "' +
                    pos[0] + '"'))
        if remember == '1':
            for book in listdir(UPLOAD_FOLDER):
                for value in ['_Collins', '_Coca']:
                    try:
                        with open(book + value + '.pk', 'rb') as input:
                            all_ex = pickle.load(input)
                            wanted_voc = pickle.load(input)

                            for v, p in all_ex.keys():
                                if voc.lower() == v.lower() and (pos[0] == p[0] or pos == 'on'):
                                    all_ex.pop((v, p))
                                    wanted_voc.pop((v, p))
                        with open(book + value + '.pk', 'wb') as output:
                            pickle.dump(all_ex, output, -1)
                            pickle.dump(wanted_voc, output, -1)
                    except Exception as e:
                        print e
        else:
            # TODO change all reletivelty directory to definitely directory(think a better directory way)
            # i TODO append wanted voc when remember
            if pos != 'on':
                for file in os.listdir(dir_path + '/../../'):
                    if file.endswith('Collins.pk') or file.endswith('Collins_up_.pk') or file.endswith(
                            'Coca.pk') or file.endswith('Coca_up_.pk'):
                        os.remove(os.path.join(dir_path + '/../../', file))
            else:
                for file in os.listdir(dir_path + '/../../'):
                    if file.endswith('Collins.pk') or file.endswith('Collins_up_.pk'):
                        os.remove(os.path.join(dir_path + '/../../', file))


                        # voc_pos_list = list()
                        # for i in request.form:
                        #     voc_pos_list.append((i, None if request.form[i] == 'on' else request.form[i]))
                        # for book in listdir(UPLOAD_FOLDER):
                        #     file_name = UPLOAD_FOLDER + '/' + book
                        #     content = pdf_miner.convert(file_name)
                        #     for value in ['_Collins']:
                        #         with open(book + value + '.pk', 'rb') as input:
                        #             all_ex = pickle.load(input)
                        #             wanted_voc = pickle.load(input)
                        #
                        #             specific_wanted_ex = file_read_output_docx.content_handle(content, db, current_app, value,
                        #                                                                       voc_pos_list)
                        #
                        #             all_ex.update(specific_wanted_ex[0])
                        #             wanted_voc.update(specific_wanted_ex[1])
                        #
                        #         with open(book + value + '.pk', 'wb') as output:
                        #             pickle.dump(all_ex, output, -1)
                        #             pickle.dump(wanted_voc, output, -1)
