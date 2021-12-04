import os

from PyPDF2 import PdfFileReader, PdfFileWriter, PdfFileMerger


class BytesLoop:
    def __init__(self, s=b''):
        self.buffer = s
        self.point = 0

    def read(self, n=-1):
        chunk = self.buffer[:n]
        self.buffer = self.buffer[n:]
        self.point -= n
        return chunk

    def write(self, s=b''):
        self.buffer += s
        self.point += len(s)

    def to_file(self, file_path=''):
        with open(file_path, 'wb+') as _file:
            _file.write(self.buffer)

    def tell(self):
        return self.point

    def get_size(self):
        return self.point / 1024


class PdfSplitter(PdfFileWriter):
    def __init__(self):
        super().__init__()

    def pop(self):
        page = self._objects.pop()
        pages = self.getObject(self._pages)
        pages.pop()
        pages["/Count"] = pages["/Count"] - 1
        return page

    def clear(self):
        super().__init__()

    def get_size(self):
        __buffer = BytesLoop()
        self.write(__buffer)
        return __buffer.get_size()


def split_pdf(file_path, output_dir, max_file_size=11 * 1024):
    assert os.path.isfile(file_path)
    assert os.path.isdir(output_dir)
    input_file_name = os.path.basename(file_path).split('.')[0]
    output_dir = os.path.join(output_dir, input_file_name)
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)
    with open(file_path, 'rb') as f:
        pdf = PdfFileReader(f)
        size = 0
        page_index = 0
        pdf_writer = PdfFileWriter()
        for i in range(0, pdf.getNumPages()):
            page = pdf.getPage(i)
            if '/Annots' in page:
                page.pop('/Annots')
            temp_writer = PdfFileWriter()
            buffer = BytesLoop()
            temp_writer.addPage(page)
            temp_writer.write(buffer)
            page_size = buffer.get_size()
            assert page_size <= max_file_size
            if size + page_size < max_file_size:
                pdf_writer.addPage(page)
                size += page_size
            else:
                pdf_writer.write(open(os.path.join(output_dir, str(page_index) + '.pdf'), 'wb+'))
                page_index += 1
                pdf_writer = PdfFileWriter()
                pdf_writer.addPage(page)
                size = page_size
        pdf_writer.write(open(os.path.join(output_dir, str(page_index) + '.pdf'), 'wb+'))
    return output_dir, page_index + 1


def join_pdf(file_path, pdf_dir, pdf_list):
    assert os.path.isdir(pdf_dir)
    pdf_list = [(os.path.join(pdf_dir, x)) for x in pdf_list]
    file_merger = PdfFileMerger()
    for pdf in pdf_list:
        file_merger.append(pdf)
    file_merger.write(file_path)
    return file_path


# file = 'science.pdf'
# page_num = split_pdf(file, './pages', 12 * 1024)
# join_pdf('new_' + file, './pages/' + file.split('.')[0], [(str(i) + '.pdf') for i in range(0, page_num)])


