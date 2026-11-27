# DavDeploy CLI authentication

The CLI will authenticate a human workspace user with the configured Cognito
user-pool client, require the user's authenticator-app code, verify the
resulting identity against the configured DavDeploy API, and keep session
tokens in the operating system credential store. It will never accept a
password or authenticator code as a command-line argument or print bearer
tokens. AWS operator credentials are separate and are not used for DavDeploy
workspace authorization.
