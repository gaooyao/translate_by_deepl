import logging
import threading
import tornado.ioloop
import tornado.web
import os
import json
import config
from config import g_data
import asyncio
from pdf_operate_handler import split_pdf, join_pdf

import httpx


class RestServer(threading.Thread):
    """
    The REST server main thread.
    """

    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)

    def run(self):
        settings = {
            "template_path": "static",
            "session_timeout": 600,
            "static_path": "static",
            "autoreload": True,
            "xsrf_cookies": False,
            "debug": True,
        }
        asyncio.set_event_loop(asyncio.new_event_loop())
        application = tornado.web.Application([
            (r'/', Index),
            (r'/query/(?P<file_name>[\S\s]+)$', Query),
            (r'/upload$', Upload),
            (r'/download/(?P<file_name>[\S\s]+)$', Download),
        ], **settings)
        application.listen(config.REST_PORT)
        tornado.ioloop.IOLoop.current().start()


class Index(tornado.web.RequestHandler):
    def get(self):
        file_list = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Title</title></head><body><form name="formPost" method="post" action="upload" enctype="multipart/form-data"><div>文件: <input name="file" type="file"/><input type="submit"></div></form><div><ul>'
        for key, value in g_data['data'].items():
            file_list += '<li>' + key + ' status: ' + value['status'] + ' '
            if value['status'] == 'ng':
                file_list += '<button onclick="window.location.href=\'' + '/query/' + key + '\'">查询</button></li>'
            else:
                file_list += '<button onclick="window.location.href=\'' + '/download/' + key + '\'">下载</button></li>'
        file_list += '</ul></div></body></html>'
        self.write(file_list)


class Query(tornado.web.RequestHandler):
    def get(self, file_name):
        if file_name not in g_data['data']:
            self.write('fail, not exist.')
            return
        status = 'ok'
        for i in g_data['data'][file_name]['sub_file']:
            if i['status'] == 'ng':
                ret = ''
                try:
                    req = httpx.post('https://api-free.deepl.com/v2/document/' + i['id'],
                                     data={'auth_key': config.auth_key, 'document_key': i['key']}, timeout=600)
                    assert req.status_code == 200
                    ret = json.loads(req.text)
                    assert ret['status'] == 'done'
                    i['status'] = 'ok'
                except Exception as e:
                    status = 'ng, '
                    if ret:
                        status += str(ret)
                    status += str(e)
                    break
        if status == 'ok':
            g_data['data'][file_name]['status'] = 'ok'
        with open('data.json', 'w') as db:
            db.write(json.dumps(g_data['data']))
        self.write(status)
        return


class Upload(tornado.web.RequestHandler):
    def post(self):
        file = self.request.files.get('file', None)[0]
        file_path = os.path.join(config.base_dir, file['filename'])
        with open(file_path, 'wb+') as f:
            f.write(file['body'])
        output_dir, file_num = split_pdf(file_path, config.base_dir, config.max_file_size)
        g_data['data'][file['filename']] = {'dir': output_dir, 'status': 'ng', 'auth_key': config.auth_key,
                                            'sub_file': []}
        for i in range(file_num):
            g_data['data'][file['filename']]['sub_file'].append({'path': os.path.join(output_dir, str(i) + '.pdf'),
                                                                 'status': 'ng', 'id': '', 'key': ''})
        for i in g_data['data'][file['filename']]['sub_file']:
            try:
                req = httpx.post('https://api-free.deepl.com/v2/document',
                                 data={'auth_key': config.auth_key, 'target_lang': config.language},
                                 files={'file': open(i['path'], 'rb')}, timeout=600)
                assert req.status_code == 200
                ret = json.loads(req.text)
                i['id'] = ret['document_id']
                i['key'] = ret['document_key']
            except Exception as e:
                print(e)
        with open('data.json', 'w') as db:
            db.write(json.dumps(g_data['data']))
        self.write('ok')


class Download(tornado.web.RequestHandler):
    def get(self, file_name):
        if file_name not in g_data['data']:
            return 'fail, not exist.'
        if g_data['data'][file_name]['status'] == 'ng':
            return 'fail, translate not finished.'
        item = g_data['data'][file_name]
        if g_data['data'][file_name]['status'] == 'dl':
            with open(os.path.join(config.base_dir, file_name.split('.')[0] + '_translated.' + file_name.split('.')[1]),
                      'rb') as f:
                self.set_header('Content-Type', 'application/octet-stream')
                self.set_header('Content-Disposition',
                                'attachment;filename=' + file_name.split('.')[0] + '_translated.' +
                                file_name.split('.')[1])
                self.write(f.read())
                self.finish()
                return
        else:
            status = 'ok'
            for i in item['sub_file']:
                if i['status'] == 'dl':
                    continue
                elif i['status'] == 'ok':
                    try:
                        req = httpx.post('https://api-free.deepl.com/v2/document/' + i['id'] + '/result',
                                         data={'auth_key': config.auth_key, 'document_key': i['key']}, timeout=600)
                        assert req.status_code == 200
                        with open(i['path'], "wb") as f:
                            f.write(req.content)
                        i['status'] = 'dl'
                    except Exception as e:
                        status = 'ng, ' + str(e)
                else:
                    status = 'ng'
            if status == 'ok':
                file = join_pdf(
                    os.path.join(config.base_dir, file_name.split('.')[0] + '_translated.' + file_name.split('.')[1]),
                    item['dir'],
                    [(str(i) + '.pdf') for i in range(0, len(item['sub_file']))])
                with open(file, 'rb') as f:
                    self.set_header('Content-Type', 'application/octet-stream')
                    self.set_header('Content-Disposition',
                                    'attachment;filename=' + file_name.split('.')[0] + '_translated.' +
                                    file_name.split('.')[1])
                    self.write(f.read())
                    g_data['data'][file_name]['status'] = 'dl'
            with open('data.json', 'w') as db:
                db.write(json.dumps(g_data['data']))
            if status != 'ok':
                self.write(status)
