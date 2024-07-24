from ldaptor.protocols import pureldap
from ldaptor.protocols.ldap.ldapclient import LDAPClient
from ldaptor.protocols.ldap.ldapconnector import connectToLDAPEndpoint
from ldaptor.protocols.ldap.proxybase import ProxyBase
from twisted.application.service import Application, Service
from twisted.internet import defer, protocol, reactor
from twisted.internet.endpoints import serverFromString
from twisted.python import log
from functools import partial
from os import environ

# Code based on https://ldaptor.readthedocs.io/en/latest/cookbook/ldap-proxy.html
# Modified by Xander Soldaat <xander@botbench.com>

class LoggingProxy(ProxyBase):
    """
    A simple example of using `ProxyBase` to log requests and responses.
    """
    def handleProxiedResponse(self, response, request, controls):
        """
        Log the representation of the responses received.
        """
        log.msg("Request => " + repr(request))
        log.msg("Response => " + repr(response))
        return defer.succeed(response)


def ldapBindRequestRepr(self):
    ldapRequestParameters = []
    ldapRequestParameters.append('version={0}'.format(self.version))
    ldapRequestParameters.append('dn={0}'.format(repr(self.dn)))
    ldapRequestParameters.append('auth=****')
    if self.tag!=self.__class__.tag:
        ldapRequestParameters.append('tag={0}'.format(self.tag))
    ldapRequestParameters.append('sasl={0}'.format(repr(self.sasl)))
    return self.__class__.__name__+'('+', '.join(ldapRequestParameters)+')'

pureldap.LDAPBindRequest.__repr__ = ldapBindRequestRepr

class LoggingProxyService(Service):

    def __init__(self, _endpointStr, _proxiedEndpointStr):
        self.endpointStr = _endpointStr
        self.proxiedEndpointStr = _proxiedEndpointStr

    def startService(self):
        factory = protocol.ServerFactory()
        use_tls = False

        clientConnector = partial(
            connectToLDAPEndpoint,
            reactor,
            self.proxiedEndpointStr,
            LDAPClient)

        def buildProtocol():
            proto = LoggingProxy()
            proto.clientConnector = clientConnector
            proto.use_tls = use_tls
            return proto

        factory.protocol = buildProtocol
        endPoint = serverFromString(reactor, self.endpointStr)
        deferredListener = endPoint.listen(factory)
        deferredListener.addCallback(self.setListeningPort)
        deferredListener.addErrback(log.err)

    def setListeningPort(self, port):
        self.port_ = port

    def stopService(self):
        # If there are asynchronous cleanup tasks that need to
        # be performed, add deferreds for them to `async_tasks`.
        async_tasks = []
        if self.port_ is not None:
            async_tasks.append(self.port_.stopListening())
        if len(async_tasks) > 0:
            return defer.DeferredList(async_tasks, consumeErrors=True)

# Get environment variables
# TODO: add cleaning up logic to avoid security issues
proxy_port = environ.get('PROXY_PORT', '10389')
proxy_endpoint_host = environ.get('PROXY_ENDPOINT_HOST', 'localhost')
proxy_endpoint_port = environ.get('PROXY_ENDPOINT_PORT', '389')

endpointStr = 'tcp:' + proxy_port
proxiedEndpointStr = 'tcp:host=' + proxy_endpoint_host + ':' + proxy_endpoint_port

application = Application("Logging LDAP Proxy")
service = LoggingProxyService(endpointStr, proxiedEndpointStr)
service.setServiceParent(application)
