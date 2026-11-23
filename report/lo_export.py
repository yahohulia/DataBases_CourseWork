"""
Виконується Python-інтерпретатором LibreOffice:
  "D:\\Programs\\LibreOffice\\program\\python.exe" report/lo_export.py <in.docx> <out.pdf>
Відкриває документ, оновлює зміст (індекси) і поля, експортує PDF.
"""
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

SOFFICE = r"D:\Programs\LibreOffice\program\soffice.exe"


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main(src, dst):
    proc = subprocess.Popen([SOFFICE, "--headless", "--invisible", "--norestore", "--nologo",
                             "--accept=socket,host=127.0.0.1,port=2002;urp;"])
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    rctx = None
    for _ in range(240):
        try:
            rctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
            break
        except Exception:
            time.sleep(1)
    desktop = rctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", rctx)
    url = uno.systemPathToFileUrl(os.path.abspath(src))
    doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", True),))
    for _ in range(2):  # двічі: номери сторінок змісту після його розгортання
        idx = doc.getDocumentIndexes()
        for i in range(idx.getCount()):
            idx.getByIndex(i).update()
        doc.getTextFields().refresh()
        doc.refresh()
    print("indexes:", doc.getDocumentIndexes().getCount())
    cursor = doc.getCurrentController().getViewCursor()
    cursor.jumpToLastPage()
    print("pages:", cursor.getPage())
    doc.storeToURL(uno.systemPathToFileUrl(os.path.abspath(dst)),
                   (prop("FilterName", "writer_pdf_Export"),))
    doc.close(True)
    try:
        desktop.terminate()
    except Exception:
        pass
    proc.wait(timeout=30)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
