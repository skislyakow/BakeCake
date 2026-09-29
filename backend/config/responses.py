from rest_framework.response import Response

OK = True
FAIL = False


def ok(**payload):
    return Response({"ok": OK, **payload}, status=200)


def fail(errors):
    return Response({"ok": FAIL, "errors": errors}, status=200)
