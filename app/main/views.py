import threading

import time
from glob import glob

from flask import render_template, session, redirect, url_for, current_app, jsonify, g, Response, make_response
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
from pyPdf import PdfFileReader
import json

dir_path = os.path.dirname(os.path.realpath(__file__))
UPLOAD_FOLDER = os.path.join(dir_path, '../upload')


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
            if file and utils.allowed_file(file.filename):
                file.save(os.path.join(UPLOAD_FOLDER, file.filename))
        for i in request.form:
            os.remove(UPLOAD_FOLDER + '/' + i)
        return redirect(url_for('.book'))
    books_list = listdir(UPLOAD_FOLDER)
    # KP: sort by data time: cool
    books_list.sort(key=lambda x: os.stat(os.path.join(UPLOAD_FOLDER, x)).st_mtime)
    return render_template('book.html', books_list=books_list)


@main.route('/dic', methods=['GET'])
def dic():
    return render_template('dic.html')


# i TODO:ADd thread to do the background thing(if db can't use, use the original mysql module instead

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
    try:
        with open(book + value + '.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)
    except Exception as e:
        print e
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
    try:
        with open(book + value + '.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)
    except Exception as e:
        print e
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


@main.route('/book_voc/<book>?value=<value>', methods=['POST', 'GET'])
@main.route('/book_voc/<book>?value=<value>?k=<k>', methods=['POST', 'GET'])
@main.route('/book_voc/<book>?value=<value>', methods=['POST', 'GET'])
@main.route('/book_voc/<book>?value=<value>?k=<k>', methods=['POST', 'GET'])
def book_voc(book, value, k=0):
    if request.method == 'POST':
        update_wanted_dic()
        return redirect(url_for('.book_voc', book=book, value=value))

    try:
        with open(book + value + '.pk', 'rb') as input:
            all_ex = pickle.load(input)
            wanted_voc = pickle.load(input)
    except Exception as e:
        print e
        file_name = UPLOAD_FOLDER + '/' + book
        pdf = PdfFileReader(open(file_name, 'rb'))
        pages = pdf.getNumPages()
        page_inter = pages / 10
        content = pdf_miner.convert(file_name, pages=[0, page_inter])
        all_ex, wanted_voc = file_read_output_docx.content_handle(content, db, current_app, value)
        vocs = list()
        for (voc_pros, word_ex_list) in (all_ex.items()):
            vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                          word_ex_list))
        return render_template('book_voc.html', page_inter=page_inter, vocs=vocs, book=book, value=value, k=k,
                               pages=pages)

    vocs = list()
    for (voc_pros, word_ex_list) in (all_ex.items()):
        vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                      word_ex_list))
    return render_template('book_voc.html', vocs=vocs, book=book, value=value, k=k)


@main.route('/test/<tt>')
def test(tt):
    return jsonify(a="a")


@main.route('/test2/')
def test2():
    return render_template('test.html', kk='k')


@main.route('/thread_book_voc/?value=<value>&book=<book>&page_inter=<page_inter>&k=<k>&pages=<pages>')
def thread_book_voc(value, book, page_inter, k, pages):
    file_name = UPLOAD_FOLDER + '/' + book
    k = int(k)
    pages = int(pages)
    page_inter = int(page_inter)
    print k
    if k * page_inter + 1 >= pages:
        with open(book + value + '_pre_.pk', 'rb') as input:
            fin_all_ex = pickle.load(input)
            fin_wanted_voc = pickle.load(input)
        with open(book + value + '.pk', 'wb') as output:
            pickle.dump(fin_all_ex, output, -1)
            pickle.dump(fin_wanted_voc, output, -1)
        return jsonify(vocs="xxx")
    content = pdf_miner.convert(file_name, [k * page_inter + 1, (k + 1) * page_inter])
    all_ex, wanted_voc = file_read_output_docx.content_handle(content, db, current_app, value)
    vocs = list()
    for (voc_pros, word_ex_list) in (all_ex.items()):
        vocs.append(utils.output_html(voc_pros[1], voc_pros[0], ''.join(list(wanted_voc[voc_pros][1][0])),
                                      word_ex_list))
    if k == 1:
        with open(book + value + '_pre_.pk', 'wb') as output:
            pickle.dump(all_ex, output, -1)
            pickle.dump(wanted_voc, output, -1)
    else:
        with open(book + value + '_pre_.pk', 'rb') as input:
            pre_all_ex = pickle.load(input)
            pre_wanted_voc = pickle.load(input)
            for i in all_ex:
                for j in pre_all_ex:
                    if i == j:
                        for g in all_ex[i]:
                            pre_all_ex[j].append(g)
                        break
                else:
                    pre_all_ex[i] = all_ex[i]
            pre_wanted_voc.update(wanted_voc)
            all_ex = pre_all_ex
            wanted_voc = pre_wanted_voc
        with open(book + value + '_pre_.pk', 'wb') as output:
            pickle.dump(all_ex, output, -1)
            pickle.dump(wanted_voc, output, -1)
    return jsonify(vocs=vocs)


def update_wanted_dic(remember="1"):
    for i in request.form:
        # for j in request.form:
        #     print j, request.form[j]
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
            # i TODO change all reletivelty directory to definitely directory(think a better directory way)
            if pos != 'on':
                for file in os.listdir(dir_path + '/../../'):
                    if file.endswith('Collins.pk') or file.endswith('Collins_pre_.pk') or file.endswith(
                            'Coca.pk') or file.endswith('Coca_pre_.pk'):
                        os.remove(os.path.join(dir_path + '/../../', file))
            else:
                for file in os.listdir(dir_path + '/../../'):
                    if file.endswith('Collins.pk') or file.endswith('Collins_pre_.pk'):
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
