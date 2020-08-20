from aiohttp.client_reqrep import ClientResponse
from aiohttp.client_exceptions import ClientResponseError


class InsanicResponse(ClientResponse):
    def raise_for_status(self):
        if 400 <= self.status:
            raise ClientResponseError(
                self.request_info,
                self.history,
                status=self.status,
                message=self.text(),
                headers=self.headers,
            )
