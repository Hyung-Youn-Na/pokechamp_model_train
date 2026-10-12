"""Observe the pinned parser loop without pre-consuming a WebSocket frame."""


class CursorMessages(list):
    def __init__(self, values, mark, offset=0):
        super().__init__(values)
        self.mark = mark
        self.offset = offset

    def __iter__(self):
        for index, value in enumerate(super().__iter__()):
            self.mark(self.offset + index)
            yield value

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(key, slice):
            start, _, step = key.indices(len(self))
            if step != 1:
                raise ValueError("unsupported protocol cursor slicing")
            return CursorMessages(value, self.mark, self.offset + start)
        return value
