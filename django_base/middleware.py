from threading import currentThread
from django.utils.deprecation import MiddlewareMixin

_requests = {}


def get_request():
    return _requests[currentThread()]


class GlobalRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        _requests[currentThread()] = request


class SingleSessionMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        from django.contrib.auth import logout
        # from django.http import JsonResponse
        if hasattr(request.user, 'customer') and \
                        request.user.customer.session_key != \
                        request.session.session_key and \
                request.user.customer.session_key:
            logout(request)
            response['FORCE_LOGOUT'] = '1'
        # if request.user.is_anonymous():
        #     response['FORCE_LOGOUT'] = '1'
        return response


class FullMediaUrlMiddleware(MiddlewareMixin):
    def process_request(self, request):
        from django.conf import settings
        from urllib.parse import urljoin
        settings.MEDIA_URL = \
            urljoin(request.get_raw_uri(), settings.MEDIA_URL)
        settings.STATIC_URL = \
            urljoin(request.get_raw_uri(), settings.STATIC_URL)
        settings.ALIPAY_NOTIFY_URL = \
            urljoin(request.get_raw_uri(), settings.ALIPAY_NOTIFY_URL)


class CookieCsrfMiddleware(MiddlewareMixin):
    def process_request(self, request):
        csrftoken = request.COOKIES.get('csrftoken')
        if csrftoken:
            request.META['HTTP_X_CSRFTOKEN'] = csrftoken


class DebugMiddleware(MiddlewareMixin):
    def process_request(self, request):
        pass


class CustomExceptionMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        import traceback
        from django.http import JsonResponse
        from sys import stderr
        from django.conf import settings
        from django.core.exceptions import ValidationError
        # Retrieves the error message, response error message only.
        msg = exception.message if hasattr(exception, 'message') else str(exception)
        # Bypass the exception raised but still print to stderr
        if settings.DEBUG or type(exception) not in [AssertionError, ValidationError]:
            print(traceback.format_exc(), file=stderr)
        # Return a client-recognizable format.
        return JsonResponse(dict(
            ok=False,
            msg=msg
        ), status=400)
