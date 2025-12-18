import requests
import uuid


def encode_fields(data):
    out = {}
    for k, v in data.items():
        if isinstance(v, bool):
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
        if "stringValue" in v:
            out[k] = v["stringValue"]
        elif "integerValue" in v:
            out[k] = int(v["integerValue"])
        elif "doubleValue" in v:
            out[k] = v["doubleValue"]
        elif "booleanValue" in v:
            out[k] = v["booleanValue"]
        elif "mapValue" in v:
            out[k] = decode_fields(v["mapValue"]["fields"])
        elif "arrayValue" in v:
            out[k] = [decode_fields({"_": i})["_"] for i in v["arrayValue"].get("values", [])]
    return out

class FirestoreREST:
    def __init__(self, project_id, database="(default)"):
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
        r = requests.post(self.url, json=payload)
        r.raise_for_status()
        return r.json()

    def stream(self):
        r = requests.get(self.url)
        r.raise_for_status()
        docs = r.json().get("documents", [])
        for d in docs:
            yield {
                "id": d["name"].split("/")[-1],
                "data": decode_fields(d["fields"])
            }


class DocumentRef:
    def __init__(self, url, doc_id):
        self.url = url
        self.id = doc_id

    def set(self, data):
        payload = {"fields": encode_fields(data)}
        r = requests.patch(self.url, json=payload)
        r.raise_for_status()

    def update(self, data):
        self.set(data)

    def get(self):
        r = requests.get(self.url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return decode_fields(r.json()["fields"])

    def delete(self):
        r = requests.delete(self.url)
        r.raise_for_status()


