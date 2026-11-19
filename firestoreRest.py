import requests
import uuid

DEFAULT_TIMEOUT = 10  # seconds; prevents the polling thread from hanging forever


def encode_fields(data):
    out = {}
    for k, v in data.items():
        if v is None:
            out[k] = {"nullValue": None}
        elif isinstance(v, bool):
            out[k] = {"booleanValue": v}
        elif isinstance(v, int):
            out[k] = {"integerValue": str(v)}
        elif isinstance(v, float):
            out[k] = {"doubleValue": v}
        elif isinstance(v, dict):
            out[k] = {"mapValue": {"fields": encode_fields(v)}}
        elif isinstance(v, list):
            out[k] = {
                "arrayValue": {
                    "values": [encode_fields({"_": i})["_"] for i in v]
                }
            }
        else:
            out[k] = {"stringValue": str(v)}
    return out


def decode_fields(fields):
    out = {}
    for k, v in fields.items():
        if "nullValue" in v:
            out[k] = None
        elif "stringValue" in v:
            out[k] = v["stringValue"]
        elif "integerValue" in v:
            out[k] = int(v["integerValue"])
        elif "doubleValue" in v:
            out[k] = v["doubleValue"]
        elif "booleanValue" in v:
            out[k] = v["booleanValue"]
        elif "mapValue" in v:
            out[k] = decode_fields(v["mapValue"].get("fields", {}))
        elif "arrayValue" in v:
            out[k] = [decode_fields({"_": i})["_"] for i in v["arrayValue"].get("values", [])]
        else:
            out[k] = None
    return out


class FirestoreREST:
    def __init__(self, project_id, database="(default)"):
        if not project_id:
            raise ValueError("project_id must be provided")
        self.base = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/{database}/documents"

    def collection(self, name):
        return CollectionRef(self.base, name)


class CollectionRef:
    def __init__(self, base, name):
        self.url = f"{base}/{name}"

    def document(self, doc_id=None):
        if doc_id is None:
            doc_id = str(uuid.uuid4())
        return DocumentRef(f"{self.url}/{doc_id}", doc_id)

    def add(self, data):
        payload = {"fields": encode_fields(data)}
        r = requests.post(self.url, json=payload, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def stream(self):
        """Yield every document in the collection, following Firestore's paging."""
        page_token = None
        for _ in range(100):  # hard cap so a misbehaving API can't loop forever
            params = {"pageSize": 300}
            if page_token:
                params["pageToken"] = page_token
            r = requests.get(self.url, params=params, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            body = r.json()
            for d in body.get("documents", []):
                yield {
                    "id": d["name"].split("/")[-1],
                    "data": decode_fields(d.get("fields", {}))
                }
            page_token = body.get("nextPageToken")
            if not page_token:
                return


class DocumentRef:
    def __init__(self, url, doc_id):
        self.url = url
        self.id = doc_id

    def set(self, data):
        payload = {"fields": encode_fields(data)}
        r = requests.patch(self.url, json=payload, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()

    def update(self, data):
        self.set(data)

    def get(self):
        r = requests.get(self.url, timeout=DEFAULT_TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return decode_fields(r.json().get("fields", {}))

    def delete(self):
        r = requests.delete(self.url, timeout=DEFAULT_TIMEOUT)
        if r.status_code == 404:
            return  # already gone — not an error for our use case
        r.raise_for_status()
