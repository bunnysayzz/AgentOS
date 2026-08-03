"""In-memory fake implementation of the google-cloud-firestore client surface
that ``app.core.db.FirestoreDB`` uses. Keeps tests fast, deterministic and
credential-free (no emulator / Java required).
"""


class _FakeSnapshot:
    def __init__(self, ref, data):
        self._ref = ref
        self._data = data
        self.exists = data is not None

    @property
    def id(self):
        return self._ref.id

    def to_dict(self):
        return dict(self._data) if self._data else {}


class _FakeDocumentRef:
    def __init__(self, coll, doc_id):
        self._coll = coll
        self.id = doc_id

    def get(self):
        return _FakeSnapshot(self, self._coll._store.get(self.id))

    def set(self, payload):
        self._coll._store[self.id] = dict(payload)

    def delete(self):
        self._coll._store.pop(self.id, None)


class _FakeCollectionRef:
    def __init__(self, name, store, filters=None):
        self._name = name
        self._store = store
        self._filters = filters or []

    def document(self, doc_id):
        return _FakeDocumentRef(self, doc_id)

    def where(self, field=None, op=None, value=None, filter=None):
        # Mirrors google-cloud-firestore: modern call sites pass
        # ``where(filter=FieldFilter(field, op, value))``; positional args are
        # the legacy form. Extract the tuple either way.
        if filter is not None:
            field = getattr(filter, "field_path", None)
            op = getattr(filter, "op_string", None)
            value = getattr(filter, "value", None)
        return _FakeCollectionRef(self._name, self._store, self._filters + [(field, op, value)])

    def _filtered(self):
        items = []
        for doc_id, data in self._store.items():
            ok = True
            for field, op, value in self._filters:
                if op == "==" and data.get(field) != value:
                    ok = False
                    break
            if ok:
                items.append(doc_id)
        return items

    def stream(self):
        for doc_id in self._filtered():
            yield _FakeSnapshot(_FakeDocumentRef(self, doc_id), self._store[doc_id])


class FakeFirestoreClient:
    """Drop-in stand-in for google.cloud.firestore.Client."""

    def __init__(self):
        self._stores = {}

    def collection(self, name):
        if name not in self._stores:
            self._stores[name] = {}
        return _FakeCollectionRef(name, self._stores[name])

    def reset(self):
        for store in self._stores.values():
            store.clear()
