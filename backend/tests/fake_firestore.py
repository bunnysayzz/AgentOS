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
    def __init__(self, name, store, filters=None, order_by=None, limit=None):
        self._name = name
        self._store = store
        self._filters = filters or []
        self._order_by = order_by
        self._limit = limit

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
        return _FakeCollectionRef(
            self._name, self._store, self._filters + [(field, op, value)],
            self._order_by, self._limit,
        )

    def order_by(self, field, direction=None):
        desc = getattr(direction, "DESCENDING", None) == "DESCENDING" or (
            getattr(direction, "value", None) == "DESCENDING"
        )
        return _FakeCollectionRef(self._name, self._store, self._filters, (field, desc), self._limit)

    def limit(self, n):
        return _FakeCollectionRef(self._name, self._store, self._filters, self._order_by, n)

    def count(self):
        return _FakeAggregationQuery(self)

    def _filtered(self):
        items = []
        for doc_id, data in self._store.items():
            ok = True
            for field, op, value in self._filters:
                if op == "==" and data.get(field) != value:
                    ok = False
                    break
                if op == ">=" and (data.get(field) or "") < value:
                    ok = False
                    break
            if ok:
                items.append(doc_id)
        return items

    def stream(self):
        ids = self._filtered()
        if self._order_by:
            field, desc = self._order_by
            ids.sort(key=lambda d: self._store[d].get(field) or "", reverse=desc)
        if self._limit is not None:
            ids = ids[: self._limit]
        for doc_id in ids:
            yield _FakeSnapshot(_FakeDocumentRef(self, doc_id), self._store[doc_id])


class _FakeAggregationResult:
    """Mimics google.cloud.firestore AggregationResult (``res[0][0].value``)."""

    def __init__(self, value):
        self.value = value

    def __getitem__(self, index):
        return self


class _FakeAggregationQuery:
    def __init__(self, coll):
        self._coll = coll

    def get(self):
        return [_FakeAggregationResult(len(self._coll._filtered()))]


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
