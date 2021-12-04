REST_PORT = 9090  # 服务器监听端口
base_dir = 'files'  # 文件存放目录
auth_key = '********'  # deepl authority key
language = 'ZH'  # 文档被翻译成的语言
max_file_size = 11 * 1024  # pdf切分大小，当11 * 1024时实际切出来的pdf为9MB左右

g_data = {'data': {}}  # 一个全局对象
