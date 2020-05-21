# satosa-microservice-webauthn
WebAuthn microservice for SATOSA that is to be used with the WebAuthn module (https://github.com/CESNET/satosa-module-webauthn)

Details about the configuration of the microservice can be found as comments in the example config file.

## Registration
Token registration is in-flow, which means that when a user tries to login to an SP
that requires MFA to be performed and they have no tokens registered, they are redirected to 
the registration page to register a token. Registration is considered a successful
authentication.

## Login and Token management
If the user tries to log in to an SP that requires MFA and they have some tokens registered, they
are redirected to the login page where they can decide
whether they want to enter the token management page after being authenticated.
