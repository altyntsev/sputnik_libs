import time

def progress(data, timeout=10):

    i, t0 = 0, 0
    if hasattr(data, '__len__'):
        n = len(data)
    else:
        n = None

    for item in data:
        t1 = time.time()
        i += 1
        if t1-t0 > timeout:
            if n:
                print(i, 'of', n)
            else:
                print(i)
            t0 = t1
        yield item