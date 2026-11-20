"""Data of harness/tls.py: the test certificates and keys, and known answers.

PEMS holds certificates and private keys made once with OpenSSL 3.0.13 by the
script GENERATED_BY below, valid from 2020 to the end of 2099 (but for the one
that expired in 2021 and the one that starts in 2098), so that no date makes
the gate fail. CHAINS says which of them a server shows together. The private
keys of the authorities are not kept. BIG, GCM, CHACHA and CBC are inputs (and,
for the ciphers, the published answers: SP 800-38D/McGrew-Viega, RFC 8439,
SP 800-38A) for the machine code of spec/tls-x86_64.s."""
PEMS={'clientonly.crt': '-----BEGIN CERTIFICATE-----\n'
                   'MIIBwTCCAWegAwIBAgIJAPekA6SxHyYQMAoGCCqGSM49BAMCMDExGTAXBgNVBAMM\n'
                   'EEFsY2hlbSBUZXN0IFJvb3QxFDASBgNVBAoMC0FsY2hlbSBUZXN0MCAXDTIwMDEw\n'
                   'MTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5WjAVMRMwEQYDVQQDDApjbGllbnRvbmx5\n'
                   'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAESpz2UOMs6CrmzevwcSpOaqwmZHir\n'
                   'CbWBIyZGHIhuECwLUBNT35np86hoJyEqiZ4D7CuJS+Ujmbxer+5yyQNBK6OBgTB/\n'
                   'MAwGA1UdEwEB/wQCMAAwEwYDVR0lBAwwCgYIKwYBBQUHAwIwGgYDVR0RBBMwEYIJ\n'
                   'bG9jYWxob3N0hwR/AAABMB0GA1UdDgQWBBQSNZbgY7TI1Ak02HB6CQgu8Dwj5TAf\n'
                   'BgNVHSMEGDAWgBRCjUpFxrruam//OYmOa+a0FScBmTAKBggqhkjOPQQDAgNIADBF\n'
                   'AiEAsBDOzcIxu1xsi1etqLj0VbEkJzMgy607yLJmIftGuG8CIBJUNTsnqTwUXjD+\n'
                   'OKjZcw7xv8MC8tD+k7FoV4tv5sUF\n'
                   '-----END CERTIFICATE-----\n',
 'clientonly.key': '-----BEGIN PRIVATE KEY-----\n'
                   'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgsD53d9/cxMAOirbB\n'
                   'N0nICTQIy3jOu45HMOcJF3fpeBGhRANCAARKnPZQ4yzoKubN6/BxKk5qrCZkeKsJ\n'
                   'tYEjJkYciG4QLAtQE1PfmenzqGgnISqJngPsK4lL5SOZvF6v7nLJA0Er\n'
                   '-----END PRIVATE KEY-----\n',
 'critical.crt': '-----BEGIN CERTIFICATE-----\n'
                 'MIIBujCCAV+gAwIBAgIIWw7cGMke8GIwCgYIKoZIzj0EAwIwMTEZMBcGA1UEAwwQ\n'
                 'QWxjaGVtIFRlc3QgUm9vdDEUMBIGA1UECgwLQWxjaGVtIFRlc3QwIBcNMjAwMTAx\n'
                 'MDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMBMxETAPBgNVBAMMCGNyaXRpY2FsMFkw\n'
                 'EwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE2+XjiWD8yb2rJL+eMxy2b4yLNBJ0YAbQ\n'
                 'qCkXI406AitnYbeaLrvM92C7UcxktZ9+8wTZT+eJ+RSt+HOvRLd61aN9MHswDAYD\n'
                 'VR0TAQH/BAIwADAaBgNVHREEEzARgglsb2NhbGhvc3SHBH8AAAEwDwYFKgMEBQYB\n'
                 'Af8EAwwBeDAdBgNVHQ4EFgQUk6V6Li5/JWR2LMRvdDwxZwVQcv4wHwYDVR0jBBgw\n'
                 'FoAUQo1KRca67mpv/zmJjmvmtBUnAZkwCgYIKoZIzj0EAwIDSQAwRgIhANTjmbWu\n'
                 'YFERE5F8XPXaCfj7kekxAR0Ky95The2jrnAMAiEA5ue3paKgTNimubDfu1MDIeTj\n'
                 'GuWZETRySBUKkqu5S8M=\n'
                 '-----END CERTIFICATE-----\n',
 'critical.key': '-----BEGIN PRIVATE KEY-----\n'
                 'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg15l4Q6567pK2ZgtC\n'
                 '6JkqA72P3R0NJ4LyWFPC+7lhvsmhRANCAATb5eOJYPzJvaskv54zHLZvjIs0EnRg\n'
                 'BtCoKRcjjToCK2dht5ouu8z3YLtRzGS1n37zBNlP54n5FK34c69Et3rV\n'
                 '-----END PRIVATE KEY-----\n',
 'deep.crt': '-----BEGIN CERTIFICATE-----\n'
             'MIIDPDCCAiSgAwIBAgIJAPvtBpoFHTDsMA0GCSqGSIb3DQEBCwUAMDkxITAfBgNV\n'
             'BAMMGEFsY2hlbSBUZXN0IEludGVybWVkaWF0ZTEUMBIGA1UECgwLQWxjaGVtIFRl\n'
             'c3QwIBcNMjAwMTAxMDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMBsxGTAXBgNVBAMM\n'
             'EEFsY2hlbSBUZXN0IERlZXAwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIB\n'
             'AQC3EfkRtnF9Ffa4p+8V2n4NxudFCOc8BiVwuBCmTxI9SHr6ojlJzkXRyZV7IFAM\n'
             'MyS+aA5iMQSkqEXSX+cvdd9oDyeDX57GhqQsWsfDXcbJNNbqqGYnr/ks8OMsomQz\n'
             'NOyay+uhEutFA5uzHYX+e5jstsp3yxxYOXkl7ZDAEa36M6gBDtevv/or0jzWL5uo\n'
             'syJIg/eV05yZujIwK6ENB3GKhfncystVMRSwa4LJK8PapZ4DrFviGC0JJOM8vdE9\n'
             'hD9uOMeEgCNMUKHugKPR0JF7GOllHSds0KQO3cclfRvDxZ8v+O/71PujqZsHbJoz\n'
             'b4qJUDzSFT+4dWoPXoIk3H4NAgMBAAGjYzBhMA8GA1UdEwEB/wQFMAMBAf8wDgYD\n'
             'VR0PAQH/BAQDAgEGMB0GA1UdDgQWBBSu1d9jApV3wwfuIeSkhlaJ/TJ7nzAfBgNV\n'
             'HSMEGDAWgBTBNVVdzTmCNg3aVBZBqDbYhv7OjjANBgkqhkiG9w0BAQsFAAOCAQEA\n'
             'SNtyjNzgkHN391NgnTrUy98dkDTsGGKufYTgq8jZl8jp7yY4RNcNFIJi5errS9yS\n'
             'KXv3CSDcEHzjwgJuo/qpwuvv3nMsX6b7jI5PfA13q7u4PFBcGFVdJkMWt9RyKm4P\n'
             'dePZxfD82kctyKtEx2c71UUTkR0nMHwk6guo07wfgMgb/iOhnvjLxH8PkwD/bxNj\n'
             'YON3ltrHagd0QXZTs7H74F/ryRbGAy2+1zMLvCr5OiZ4kjYWr4YeqLQPDzvlRO7K\n'
             'fm1J5iP0xd0Q50qyYCz3i7cwyU9W/z26Jhncjr1etHcUgzWUAd+TbtJwgwPhzES2\n'
             'zbMCN3R7MTgtv1jLvejUJg==\n'
             '-----END CERTIFICATE-----\n',
 'empty.txt': 'no pem here\n',
 'enc.key': '-----BEGIN ENCRYPTED PRIVATE KEY-----\n'
            'MIHsMFcGCSqGSIb3DQEFDTBKMCkGCSqGSIb3DQEFDDAcBAgndPuA3r/geQICCAAw\n'
            'DAYIKoZIhvcNAgkFADAdBglghkgBZQMEASoEECKO3npLj4Ag2F64fqT+HoQEgZBw\n'
            'Y9zKDwYY3Ohox+GVt+/+2B3+kzLhtCNjP0AZNsoumUOa+8AuErLgdsGJo3tZb4ny\n'
            'xMeqtV2GOucgsEOO1DqnrA7RIZhcuC7/dkdXtDb1pb+zKUSNnQy4BWSkUx843GsD\n'
            '4eyTPm8tXP97k72FZ+TzOB0vM+7IveD4kEVe9EL8+fYB9r88S6Gj/Qpo+zaq3zc=\n'
            '-----END ENCRYPTED PRIVATE KEY-----\n',
 'expired.crt': '-----BEGIN CERTIFICATE-----\n'
                'MIIB7zCCAZWgAwIBAgIJAOZbCwUZBDhIMAoGCCqGSM49BAMCMDExGTAXBgNVBAMM\n'
                'EEFsY2hlbSBUZXN0IFJvb3QxFDASBgNVBAoMC0FsY2hlbSBUZXN0MB4XDTIwMDEw\n'
                'MTAwMDAwMFoXDTIxMDEwMTAwMDAwMFowEjEQMA4GA1UEAwwHZXhwaXJlZDBZMBMG\n'
                'ByqGSM49AgEGCCqGSM49AwEHA0IABMB8UKuefyXxuTddSvVtNvZv+MLFgP+a9VQa\n'
                'T8c+lZ4oeM5swfIT8pgNltLlhrEcdzmsXUF9lZJgjZK1K9224A2jgbQwgbEwDAYD\n'
                'VR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCBaAwEwYDVR0lBAwwCgYIKwYBBQUHAwEw\n'
                'PAYDVR0RBDUwM4IJbG9jYWxob3N0gg4qLmV4YW1wbGUudGVzdIcEfwAAAYcQAAAA\n'
                'AAAAAAAAAAAAAAAAATAfBgNVHSMEGDAWgBRCjUpFxrruam//OYmOa+a0FScBmTAd\n'
                'BgNVHQ4EFgQU9FQv0AOhmPTmyFYkZ3yzGbJax0cwCgYIKoZIzj0EAwIDSAAwRQIh\n'
                'AJs5mBGhGGs5TiYsNsObxxugW7rGf+yAuvffQfPki7rWAiBNf/SiIQT+X+Tx4wON\n'
                'ARFWuGN46/IjJIFdsofXfaiCRg==\n'
                '-----END CERTIFICATE-----\n',
 'expired.key': '-----BEGIN PRIVATE KEY-----\n'
                'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgdCh6Y5uiocbQ4PQ1\n'
                'CfbyGZfdqVLD7iWvlAtgRiBBTO6hRANCAATAfFCrnn8l8bk3XUr1bTb2b/jCxYD/\n'
                'mvVUGk/HPpWeKHjObMHyE/KYDZbS5YaxHHc5rF1BfZWSYI2StSvdtuAN\n'
                '-----END PRIVATE KEY-----\n',
 'foo.pem': '-----BEGIN FOO-----\n'
            'AAAA\n'
            '-----END FOO-----\n'
            '-----BEGIN BAR-----\n'
            'AAAA\n'
            '-----END BAR-----\n',
 'future.crt': '-----BEGIN CERTIFICATE-----\n'
               'MIIB8jCCAZigAwIBAgIJALdC2NXAo175MAoGCCqGSM49BAMCMDExGTAXBgNVBAMM\n'
               'EEFsY2hlbSBUZXN0IFJvb3QxFDASBgNVBAoMC0FsY2hlbSBUZXN0MCIYDzIwOTgw\n'
               'MTAxMDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMBExDzANBgNVBAMMBmZ1dHVyZTBZ\n'
               'MBMGByqGSM49AgEGCCqGSM49AwEHA0IABDLTYLVRq2pw9z+aQCO9v5hE0ThG/Wdg\n'
               'YygiPnNWnBvO9utRqeG5kYcq2Ejbo0uYZgjSurQLK1MMjkQagD2vETujgbQwgbEw\n'
               'DAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCBaAwEwYDVR0lBAwwCgYIKwYBBQUH\n'
               'AwEwPAYDVR0RBDUwM4IJbG9jYWxob3N0gg4qLmV4YW1wbGUudGVzdIcEfwAAAYcQ\n'
               'AAAAAAAAAAAAAAAAAAAAATAfBgNVHSMEGDAWgBRCjUpFxrruam//OYmOa+a0FScB\n'
               'mTAdBgNVHQ4EFgQUyxE9ztPv8KWvtNSiSydHJAWLvH8wCgYIKoZIzj0EAwIDSAAw\n'
               'RQIhAKtccAkfE/ep7AdXtkOtrHqq/S9s9YDzNE5ZHh0i+5gmAiA2lUYeIvd8KFmR\n'
               'HO7oU+0hPPJ/PlgYp9+YvCAj42wjUA==\n'
               '-----END CERTIFICATE-----\n',
 'future.key': '-----BEGIN PRIVATE KEY-----\n'
               'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgJFIZCxWvXFXjx2W6\n'
               'V+vMJ2dnZUmo8LN54WEpZWDevBGhRANCAAQy02C1UatqcPc/mkAjvb+YRNE4Rv1n\n'
               'YGMoIj5zVpwbzvbrUanhuZGHKthI26NLmGYI0rq0CytTDI5EGoA9rxE7\n'
               '-----END PRIVATE KEY-----\n',
 'garbage.crt': '-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n',
 'garbage.key': '-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n',
 'inter.crt': '-----BEGIN CERTIFICATE-----\n'
              'MIICkzCCAjigAwIBAgIHZTRjpMJWVTAKBggqhkjOPQQDAjAxMRkwFwYDVQQDDBBB\n'
              'bGNoZW0gVGVzdCBSb290MRQwEgYDVQQKDAtBbGNoZW0gVGVzdDAgFw0yMDAxMDEw\n'
              'MDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowOTEhMB8GA1UEAwwYQWxjaGVtIFRlc3Qg\n'
              'SW50ZXJtZWRpYXRlMRQwEgYDVQQKDAtBbGNoZW0gVGVzdDCCASIwDQYJKoZIhvcN\n'
              'AQEBBQADggEPADCCAQoCggEBAMvt1+DfpVCUPZ+U8DsdMyq4Vma7TT//s3TJFf60\n'
              'jHv7v9a1H98wXQI7gG+aeclzBYfUSiuBQypiJVhzf4fYyIdDqJeTM6qEr22QxSLH\n'
              'Ke2T56TS/IGrd0oueOrGg3v0Fxhz50zSHCH/YCodgN5ZVZXqlCk+F0EmFuAZjG9d\n'
              'WHoaFPxit4TOvwYGlVFnPBBz+YjSPinj9KO4M6ppJf3GUuTiBRud8Kii4EkW+g7S\n'
              'ZkrcTincKnBZzDPC333BJMH5NhWpD7tMIz66GqrK5s5MR9Ca0Qtd+7UbZYOUJOaX\n'
              'hdy3ctnrZaI+/eRmb+YFIk3/GzVsIpic0MvV4TqK7PQA8fkCAwEAAaNmMGQwEgYD\n'
              'VR0TAQH/BAgwBgEB/wIBADAOBgNVHQ8BAf8EBAMCAQYwHQYDVR0OBBYEFME1VV3N\n'
              'OYI2DdpUFkGoNtiG/s6OMB8GA1UdIwQYMBaAFEKNSkXGuu5qb/85iY5r5rQVJwGZ\n'
              'MAoGCCqGSM49BAMCA0kAMEYCIQDBe7NIeMev+gK5zTq91nuazUEYcSj7aR+BCckU\n'
              'Loq7aAIhAIwn0pc0FBDtfhdz8d7zzqPcU5UOhncVY4UAbnMG3Hne\n'
              '-----END CERTIFICATE-----\n',
 'leaf-ed.crt': '-----BEGIN CERTIFICATE-----\n'
                'MIICizCCAXOgAwIBAgIJAOcXnasuixEkMA0GCSqGSIb3DQEBCwUAMDkxITAfBgNV\n'
                'BAMMGEFsY2hlbSBUZXN0IEludGVybWVkaWF0ZTEUMBIGA1UECgwLQWxjaGVtIFRl\n'
                'c3QwIBcNMjAwMTAxMDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMBIxEDAOBgNVBAMM\n'
                'B2xlYWYgZWQwKjAFBgMrZXADIQCy4tAVXN+1LXDDnRH7csQLJYF5dctcNz/79Izz\n'
                'v6fSAqOBtDCBsTAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIFoDATBgNVHSUE\n'
                'DDAKBggrBgEFBQcDATA8BgNVHREENTAzgglsb2NhbGhvc3SCDiouZXhhbXBsZS50\n'
                'ZXN0hwR/AAABhxAAAAAAAAAAAAAAAAAAAAABMB8GA1UdIwQYMBaAFME1VV3NOYI2\n'
                'DdpUFkGoNtiG/s6OMB0GA1UdDgQWBBS6lmlxxd2JujwnrPLKaFSVcnGSCzANBgkq\n'
                'hkiG9w0BAQsFAAOCAQEAd70To6s7AgmLx3QzeNPn5fBePC1KnpqU/HQtJayLKWBn\n'
                'fqfyH0Bxvhp/aY7YhQh21UR3A139zis+oaBc+EL+QA0Fuioy2bhZ8zvWB6zfp6ho\n'
                'l6CKneHgKeBXaA6XkippuE/xuiKgxjxlBcIw5ca+31hr6ZcCjp/8lX8bU9M6i/eb\n'
                'PNTirjjD31H29RsnFGoXoVbJGgGDFp/EtW++1MgxgImoKO+ho+EgcAuj2/1f8OZU\n'
                'MhbYw6pnc6RJ8Tr95KdMbezSkBAIW8GXDTwvnCwHkAroYjOSrbgGo+m9mzyKq6zi\n'
                'EBpXjnMngvsP/2xHAMvPx/cUv3Q67Qo6zl5c6Xnozw==\n'
                '-----END CERTIFICATE-----\n',
 'leaf-ed.key': '-----BEGIN PRIVATE KEY-----\n'
                'MC4CAQAwBQYDK2VwBCIEIHN9aCJsvZQWkf1HoeLkm0cZv7piENp0auxKynyBQEk3\n'
                '-----END PRIVATE KEY-----\n',
 'leaf-p256.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIICvDCCAaSgAwIBAgIJALxHUT/Km3gQMA0GCSqGSIb3DQEBCwUAMDkxITAfBgNV\n'
                  'BAMMGEFsY2hlbSBUZXN0IEludGVybWVkaWF0ZTEUMBIGA1UECgwLQWxjaGVtIFRl\n'
                  'c3QwIBcNMjAwMTAxMDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMBQxEjAQBgNVBAMM\n'
                  'CWxlYWYgcDI1NjBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABLoBWyQ0eHZoZoI1\n'
                  '++saAu7i+hbohB3/Wn5SePSpcWHUMbh0ru8krrQoBUHm6L2gaOyWaAdttoqdj1HY\n'
                  'YJDuhr6jgbQwgbEwDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCBaAwEwYDVR0l\n'
                  'BAwwCgYIKwYBBQUHAwEwPAYDVR0RBDUwM4IJbG9jYWxob3N0gg4qLmV4YW1wbGUu\n'
                  'dGVzdIcEfwAAAYcQAAAAAAAAAAAAAAAAAAAAATAfBgNVHSMEGDAWgBTBNVVdzTmC\n'
                  'Ng3aVBZBqDbYhv7OjjAdBgNVHQ4EFgQUH0J8qPERcQaF9aqOexy0dvbRilMwDQYJ\n'
                  'KoZIhvcNAQELBQADggEBAEIrmE3iaRYXNVMTi7O37M2lxV8T/tK8LqRGUNLdWAzI\n'
                  'pBPfvXkw81g24dGoxk6Be6anssJjq5YiMAw74OQzyfcnXSJXgeZIW49F3RdgWFYl\n'
                  'Lm2fbBxD+fg63LEijh9aytqO6mNgb9RZ6yQiiUJrg3dTn6AVdKE8Kw4GlZdC8PbL\n'
                  'mfmZBbv6gxxXRW8xhJeM1j+TgXu6ulNnBVaqOCYlyYYYxa043ogCvhaXhLXHS81O\n'
                  'L0zZj9H0GkPzsoAqH63NwrXWCq7e4PGcoWBin9ZQ9+LoMxLiyhyDLIonKZD7XvI5\n'
                  'rapFmjzNK3gazxqbOJpYhJqoOMMrzx8B6FLdOMXYDag=\n'
                  '-----END CERTIFICATE-----\n',
 'leaf-p256.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg2Npp3S349wNENskZ\n'
                  'OzLUOVpeWm3PikNb+My7JiHSniGhRANCAAS6AVskNHh2aGaCNfvrGgLu4voW6IQd\n'
                  '/1p+Unj0qXFh1DG4dK7vJK60KAVB5ui9oGjslmgHbbaKnY9R2GCQ7oa+\n'
                  '-----END PRIVATE KEY-----\n',
 'leaf-p256.sec1.key': '-----BEGIN EC PRIVATE KEY-----\n'
                       'MHcCAQEEINjaad0t+PcDRDbJGTsy1DlaXlptz4pDW/jMuyYh0p4hoAoGCCqGSM49\n'
                       'AwEHoUQDQgAEugFbJDR4dmhmgjX76xoC7uL6FuiEHf9aflJ49KlxYdQxuHSu7ySu\n'
                       'tCgFQebovaBo7JZoB222ip2PUdhgkO6Gvg==\n'
                       '-----END EC PRIVATE KEY-----\n',
 'leaf-p384.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIIC2DCCAcCgAwIBAgIIA3Nlq2LImjowDQYJKoZIhvcNAQELBQAwOTEhMB8GA1UE\n'
                  'AwwYQWxjaGVtIFRlc3QgSW50ZXJtZWRpYXRlMRQwEgYDVQQKDAtBbGNoZW0gVGVz\n'
                  'dDAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowFDESMBAGA1UEAwwJ\n'
                  'bGVhZiBwMzg0MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAEfooxuY0iKrrSOd9Ad4Of\n'
                  'MCRh2RoJVGZy85q0D2tBpDURXJ5lBrnh6Mdvc2BI8rf27p+66GNCNBQX1Sv5NnOa\n'
                  'Zj/dglT+Q4irtAeMbYkOAnyscyjPHsxREtPoqIfbKKvMo4G0MIGxMAwGA1UdEwEB\n'
                  '/wQCMAAwDgYDVR0PAQH/BAQDAgWgMBMGA1UdJQQMMAoGCCsGAQUFBwMBMDwGA1Ud\n'
                  'EQQ1MDOCCWxvY2FsaG9zdIIOKi5leGFtcGxlLnRlc3SHBH8AAAGHEAAAAAAAAAAA\n'
                  'AAAAAAAAAAEwHwYDVR0jBBgwFoAUwTVVXc05gjYN2lQWQag22Ib+zo4wHQYDVR0O\n'
                  'BBYEFEd90isqkMsGvG3JKs31ucDCmhw6MA0GCSqGSIb3DQEBCwUAA4IBAQBbFqWO\n'
                  'zO0dG8zhm0ZHNF3tbwqx3kpqeqRt3h4nNfv2rWuMTh5sv8LUjiSHQoSrTek7TOgR\n'
                  '/gdYB5pZmRGaohCH+qeB5+n4kaG6CmR5sbcwI7TEf4ldzgSUXfwE2IfcKHkxYxEg\n'
                  'Br3+5YZ4SrwuiJaglCIWWYU4/wcfFHNvi1I7d/uapyj1IfAxYvYj2LlKNFaMn+WM\n'
                  'FHqU582aIjdSaVlpVLqi9YMtTplFfUJyoLsTBHEJgjOpzKzBb8GvUbk5fMulm6Nl\n'
                  '0b/jfcEalHxQj6XVTaj/anYQ6FBVq921zlRxq67fLVMT5X0l7ttRdUXnh6AwYn+J\n'
                  '+rzJNgTKPoKUpB9q\n'
                  '-----END CERTIFICATE-----\n',
 'leaf-p384.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIG2AgEAMBAGByqGSM49AgEGBSuBBAAiBIGeMIGbAgEBBDDJ4kFPgOjXGneG46EQ\n'
                  '/vc1NA82GG07Ttpu1rc+ItrN3ET6U6ih4DGfQnFp5wts9QGhZANiAAR+ijG5jSIq\n'
                  'utI530B3g58wJGHZGglUZnLzmrQPa0GkNRFcnmUGueHox29zYEjyt/bun7roY0I0\n'
                  'FBfVK/k2c5pmP92CVP5DiKu0B4xtiQ4CfKxzKM8ezFES0+ioh9soq8w=\n'
                  '-----END PRIVATE KEY-----\n',
 'leaf-p521.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIIC/jCCAeagAwIBAgIICR0eCqPC9hcwDQYJKoZIhvcNAQELBQAwOTEhMB8GA1UE\n'
                  'AwwYQWxjaGVtIFRlc3QgSW50ZXJtZWRpYXRlMRQwEgYDVQQKDAtBbGNoZW0gVGVz\n'
                  'dDAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowFDESMBAGA1UEAwwJ\n'
                  'bGVhZiBwNTIxMIGbMBAGByqGSM49AgEGBSuBBAAjA4GGAAQBBlnH6MxSh7yJEHvR\n'
                  '41sLqlXt4pv2Ndd6cDLLxfVz73bnEbrgeNT2zCTmwuWZWE29tLavOKCRjfUywPUE\n'
                  'o7IlhqgA3qCTWEE8spKtk0y+8/cgPSx679BnCM3aHxAzg7nLVyZIm8mY3my8Un9Y\n'
                  '3NcXZLqxYJgPeYmGViG/taC1NvdJIAOjgbQwgbEwDAYDVR0TAQH/BAIwADAOBgNV\n'
                  'HQ8BAf8EBAMCBaAwEwYDVR0lBAwwCgYIKwYBBQUHAwEwPAYDVR0RBDUwM4IJbG9j\n'
                  'YWxob3N0gg4qLmV4YW1wbGUudGVzdIcEfwAAAYcQAAAAAAAAAAAAAAAAAAAAATAf\n'
                  'BgNVHSMEGDAWgBTBNVVdzTmCNg3aVBZBqDbYhv7OjjAdBgNVHQ4EFgQUU+/aE/NA\n'
                  'OLVKoYHfaUjj4Cm23BkwDQYJKoZIhvcNAQELBQADggEBAF5bzvHX2m9LVq6fC0/q\n'
                  'ahj1MxK93+bEvoN6QjsfQOzB8bLreyjPXR2u9OgdPCBkR+RarlxKxBq7zYd35Jc6\n'
                  'h5M0IelApGJKq1IaHrrVVn5HEkIU3YqwPBKXtzmBXXlftt0cNyahR9gmyab2IB3k\n'
                  'xz0dLN+5pjORFk1uWpBIUhjk2obgDT24TWu0p9MKZCwTu1kkxdWzXjAPS+VrtA53\n'
                  'YiaDsTCqR7xmbCRQf43RkF2hcxYox420x+5V5EW8pCKUerVrRs15skmeaLnN+Zbv\n'
                  'b//6W0WOs6saUwi8A8QyusPrwN1BQI3IkmyNugRAoIbULtpdxqMp00Vdm1h78e2d\n'
                  '4ws=\n'
                  '-----END CERTIFICATE-----\n',
 'leaf-p521.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIHuAgEAMBAGByqGSM49AgEGBSuBBAAjBIHWMIHTAgEBBEIAvLJDkHSYyj833SdO\n'
                  'a3K8P0vsFAL3HjnWGlGTQL2oxk3HuFSpzA8XkfkjKFTp22DdNqovHDLmTWD8Jwfh\n'
                  'fIksEUGhgYkDgYYABAEGWcfozFKHvIkQe9HjWwuqVe3im/Y113pwMsvF9XPvducR\n'
                  'uuB41PbMJObC5ZlYTb20tq84oJGN9TLA9QSjsiWGqADeoJNYQTyykq2TTL7z9yA9\n'
                  'LHrv0GcIzdofEDODuctXJkibyZjebLxSf1jc1xdkurFgmA95iYZWIb+1oLU290kg\n'
                  'Aw==\n'
                  '-----END PRIVATE KEY-----\n',
 'leaf-rsa.crt': '-----BEGIN CERTIFICATE-----\n'
                 'MIIDhTCCAm2gAwIBAgIIJkHqkUXld0MwDQYJKoZIhvcNAQELBQAwOTEhMB8GA1UE\n'
                 'AwwYQWxjaGVtIFRlc3QgSW50ZXJtZWRpYXRlMRQwEgYDVQQKDAtBbGNoZW0gVGVz\n'
                 'dDAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowEzERMA8GA1UEAwwI\n'
                 'bGVhZiByc2EwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCNwyru901G\n'
                 'xOJtykVy2RUjOKH4KQEvsbCNmoo2tmaCQ1EV/o8Tn60DBg+/D7VHJmp2fu9bSxX/\n'
                 'N2nuXihtlyH6/x+jc9LGAVxAxMVHd8nx717Kxe2XSoGbQZHEcSoTVBP3e/E8yVDe\n'
                 'k7GInMVeBbqVLUXVX8b3vuPYnG3LIsqLqUIGAIKHiosPf43Avlu8iUItOzGyJi4k\n'
                 'RXkIC1ZQzXn1yGSwLD3pmKVU+kuH8TUUAUK2fqfSsRJNrtTtIANtEW3Iv9amuHHk\n'
                 'WADLyemKMgTxYGlWGW7L1+Ysj4klVmN/B/qm8si9Ds6h5er0SgcOxZhpPXAd46Xr\n'
                 'Joj5azXX7XFtAgMBAAGjgbQwgbEwDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMC\n'
                 'BaAwEwYDVR0lBAwwCgYIKwYBBQUHAwEwPAYDVR0RBDUwM4IJbG9jYWxob3N0gg4q\n'
                 'LmV4YW1wbGUudGVzdIcEfwAAAYcQAAAAAAAAAAAAAAAAAAAAATAfBgNVHSMEGDAW\n'
                 'gBTBNVVdzTmCNg3aVBZBqDbYhv7OjjAdBgNVHQ4EFgQUdqZ1JIYqTwfmBcTq1IUU\n'
                 'PzrvciMwDQYJKoZIhvcNAQELBQADggEBAAw+EcR39hgI3nIo/npj2JsALZ7kZZJw\n'
                 'IYwCpxVqoo/7g1yGu0lE22cOWHlbQXtZofPDO1xdelY9otMMljighpUEcu/0WUh2\n'
                 'fmQm0KKo5PdtTLzsai8YxQjPe8FzVVSSpBLueiXyKfugC97lmxNthcQlowFZfAKr\n'
                 'aYh2CBnbhPxSGkLvqkVg6dmfWLP1QzYqjAkQgfE+PcKnT9ALokpmdqKN+N2uqT5c\n'
                 'Tfz6hrtRZOJrEp9nZvVHQN72YLrGJq74agVk9kWBeEIEXXyoX/g5HQdpPUycdQ0/\n'
                 'JQgyDoBexIfyYVnMIGjBOz4TWYLqYjTbqG0O2kc8NNfiAqLGtIf+2QE=\n'
                 '-----END CERTIFICATE-----\n',
 'leaf-rsa.key': '-----BEGIN PRIVATE KEY-----\n'
                 'MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCNwyru901GxOJt\n'
                 'ykVy2RUjOKH4KQEvsbCNmoo2tmaCQ1EV/o8Tn60DBg+/D7VHJmp2fu9bSxX/N2nu\n'
                 'XihtlyH6/x+jc9LGAVxAxMVHd8nx717Kxe2XSoGbQZHEcSoTVBP3e/E8yVDek7GI\n'
                 'nMVeBbqVLUXVX8b3vuPYnG3LIsqLqUIGAIKHiosPf43Avlu8iUItOzGyJi4kRXkI\n'
                 'C1ZQzXn1yGSwLD3pmKVU+kuH8TUUAUK2fqfSsRJNrtTtIANtEW3Iv9amuHHkWADL\n'
                 'yemKMgTxYGlWGW7L1+Ysj4klVmN/B/qm8si9Ds6h5er0SgcOxZhpPXAd46XrJoj5\n'
                 'azXX7XFtAgMBAAECggEACaVzqPIcCIpCLB1c7201IoHqh5PmuEObk28mI4Xy4L9K\n'
                 '57e8LaYqZC/H54TenXpQOUL275vi4cx4AVfX4Wksz0MH+Jvbhky2ZdPd5riQfc1/\n'
                 'gkXInohb3GAwVpEqv0jz2N3Oswex4ItlQ7oDNhwmr5r2iwfq5pXPNECkufNim/Et\n'
                 'EOTXX4jAU7Cmm/m1TZTBPdbWFrkBcI1EpNm31A42k2HiOZJwQD4roitHhRW5Gmb1\n'
                 '9X90qoCX0/wj5AfaJK41fFHx9CUdlbEsDMPnMCKSjLECEJuaWZmcoVPLy4brUbq6\n'
                 'tMoY8+dT0p6dGiq2xsMO51ifATBYaclGRaRFUQT3cwKBgQDHG6WTAsR9MXsLB6Zq\n'
                 'qPUkDafjiizuZwyd9xMw6gh7zQ5Ttz1gbmM71ACWOrvZTDl5XP7arxIWvjuwAUYG\n'
                 'NQhvV/1IxqCpORuURffyFvFj/2E2t8yBQkoG1QrdbMPqpkpy1KjMD1l52q6zYq5a\n'
                 'MXfAl30NOqpSC3/4UhdigGfRewKBgQC2RM2PJFNARc7gbik7xe8sTA9rkra8P5ta\n'
                 'NnaK9v+gAi5r0bc4fMNauykzUIYlYab8ut0penXyiw9haruGh/O+i+NYgwF/UM68\n'
                 'm2hJItdOwQ4qdcqP9GNZtIxT0IbT2saEqb5G2LBhnIJ2hsw3AyTROSMwlSHfIcVj\n'
                 'c5pDuatQNwKBgGtZ7ajY2iYB8qxcwI5LcHiy4C1fh6A2cWgOGgvKcy6Evc/HQVFn\n'
                 '0xsjz/kvy656WZak3Ef+Eouun7HizeV03Ipj7404gtEamFMWcnvVgOsAe2KsMJgU\n'
                 'rKMIZKZECVHPvN4y6Ju1PvHjRUQ01XqNp1pwkxz533EDAElbwX37a35XAoGBAIRN\n'
                 'bvRvRqrJwT/xVqbXpyN9VlgcV95PQWH7VJLMdYLc8ns68AblsRvj7SUdVzI9LuwW\n'
                 'a8DW7lSPEiwBQHuHparzeaPe/DBBJL+NAubLjoPQ6IpzlARoPdF4l7+jBqszC5Ry\n'
                 'bfaZBXblF2IXuJZaBtiD5AI4zixcJB5rZFeypyKDAoGADrwDlrGd561hoOHNjYFs\n'
                 '4OEmxXNiYhLm9SiX/waBpuHp1yUsKPUVDCkFsxifa9AUM8oiV9KsB9y1pauTPk6A\n'
                 'insqm6D8xNx0KcMe3zx88ocd34rM6rvTLVGA1sTDXoRydo3S7oxyxM0aAgCHG+x4\n'
                 'hkBc3M8jD5mc5SjBV0zCKjk=\n'
                 '-----END PRIVATE KEY-----\n',
 'leaf-rsa.pkcs1.key': '-----BEGIN RSA PRIVATE KEY-----\n'
                       'MIIEowIBAAKCAQEAjcMq7vdNRsTibcpFctkVIzih+CkBL7GwjZqKNrZmgkNRFf6P\n'
                       'E5+tAwYPvw+1RyZqdn7vW0sV/zdp7l4obZch+v8fo3PSxgFcQMTFR3fJ8e9eysXt\n'
                       'l0qBm0GRxHEqE1QT93vxPMlQ3pOxiJzFXgW6lS1F1V/G977j2JxtyyLKi6lCBgCC\n'
                       'h4qLD3+NwL5bvIlCLTsxsiYuJEV5CAtWUM159chksCw96ZilVPpLh/E1FAFCtn6n\n'
                       '0rESTa7U7SADbRFtyL/Wprhx5FgAy8npijIE8WBpVhluy9fmLI+JJVZjfwf6pvLI\n'
                       'vQ7OoeXq9EoHDsWYaT1wHeOl6yaI+Ws11+1xbQIDAQABAoIBAAmlc6jyHAiKQiwd\n'
                       'XO9tNSKB6oeT5rhDm5NvJiOF8uC/Sue3vC2mKmQvx+eE3p16UDlC9u+b4uHMeAFX\n'
                       '1+FpLM9DB/ib24ZMtmXT3ea4kH3Nf4JFyJ6IW9xgMFaRKr9I89jdzrMHseCLZUO6\n'
                       'AzYcJq+a9osH6uaVzzRApLnzYpvxLRDk11+IwFOwppv5tU2UwT3W1ha5AXCNRKTZ\n'
                       't9QONpNh4jmScEA+K6IrR4UVuRpm9fV/dKqAl9P8I+QH2iSuNXxR8fQlHZWxLAzD\n'
                       '5zAikoyxAhCbmlmZnKFTy8uG61G6urTKGPPnU9KenRoqtsbDDudYnwEwWGnJRkWk\n'
                       'RVEE93MCgYEAxxulkwLEfTF7Cwemaqj1JA2n44os7mcMnfcTMOoIe80OU7c9YG5j\n'
                       'O9QAljq72Uw5eVz+2q8SFr47sAFGBjUIb1f9SMagqTkblEX38hbxY/9hNrfMgUJK\n'
                       'BtUK3WzD6qZKctSozA9Zedqus2KuWjF3wJd9DTqqUgt/+FIXYoBn0XsCgYEAtkTN\n'
                       'jyRTQEXO4G4pO8XvLEwPa5K2vD+bWjZ2ivb/oAIua9G3OHzDWrspM1CGJWGm/Lrd\n'
                       'KXp18osPYWq7hofzvovjWIMBf1DOvJtoSSLXTsEOKnXKj/RjWbSMU9CG09rGhKm+\n'
                       'RtiwYZyCdobMNwMk0TkjMJUh3yHFY3OaQ7mrUDcCgYBrWe2o2NomAfKsXMCOS3B4\n'
                       'suAtX4egNnFoDhoLynMuhL3Px0FRZ9MbI8/5L8uuelmWpNxH/hKLrp+x4s3ldNyK\n'
                       'Y++NOILRGphTFnJ71YDrAHtirDCYFKyjCGSmRAlRz7zeMuibtT7x40VENNV6jada\n'
                       'cJMc+d9xAwBJW8F9+2t+VwKBgQCETW70b0aqycE/8Vam16cjfVZYHFfeT0Fh+1SS\n'
                       'zHWC3PJ7OvAG5bEb4+0lHVcyPS7sFmvA1u5UjxIsAUB7h6Wq83mj3vwwQSS/jQLm\n'
                       'y46D0OiKc5QEaD3ReJe/owarMwuUcm32mQV25RdiF7iWWgbYg+QCOM4sXCQea2RX\n'
                       'sqcigwKBgA68A5axneetYaDhzY2BbODhJsVzYmIS5vUol/8Ggabh6dclLCj1FQwp\n'
                       'BbMYn2vQFDPKIlfSrAfctaWrkz5OgIp7Kpug/MTcdCnDHt88fPKHHd+KzOq70y1R\n'
                       'gNbEw16EcnaN0u6McsTNGgIAhxvseIZAXNzPIw+ZnOUowVdMwio5\n'
                       '-----END RSA PRIVATE KEY-----\n',
 'nc-bad.crt': '-----BEGIN CERTIFICATE-----\n'
               'MIIBmzCCAUCgAwIBAgIJAJHoRJScJFeYMAoGCCqGSM49BAMCMDgxIDAeBgNVBAMM\n'
               'F0FsY2hlbSBUZXN0IENvbnN0cmFpbmVkMRQwEgYDVQQKDAtBbGNoZW0gVGVzdDAg\n'
               'Fw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowETEPMA0GA1UEAwwGbmMg\n'
               'YmFkMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAElX97An3CbIGQBULf9nXqspZj\n'
               'PnQpHc+uGpbHxAv8Y6e0WUSnukcv1SoJBDzGY2MED08AVxkT8GdTAGZKuCwUVKNY\n'
               'MFYwFAYDVR0RBA0wC4IJbG9jYWxob3N0MB0GA1UdDgQWBBTOXWz8a5LVTopRtL3n\n'
               'zrhPvD+oFTAfBgNVHSMEGDAWgBTisKpcdVjRDDc7EtQ/eiI26Sw1mzAKBggqhkjO\n'
               'PQQDAgNJADBGAiEAlZsplj1bqgORbUSqa6o9+swAS43yqxNhyoae/YGFRowCIQDm\n'
               'u0aLiMHHiT5cJsUiqN9lEe8BYGmiECwT26NhA7JLNw==\n'
               '-----END CERTIFICATE-----\n',
 'nc-bad.key': '-----BEGIN PRIVATE KEY-----\n'
               'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgpLveACkEFlPreBn/\n'
               'zOd2mF/CgLsabrErPKO83KUE0nuhRANCAASVf3sCfcJsgZAFQt/2deqylmM+dCkd\n'
               'z64alsfEC/xjp7RZRKe6Ry/VKgkEPMZjYwQPTwBXGRPwZ1MAZkq4LBRU\n'
               '-----END PRIVATE KEY-----\n',
 'nc-excl.crt': '-----BEGIN CERTIFICATE-----\n'
                'MIIBoDCCAUegAwIBAgIIAlAjGpXg02kwCgYIKoZIzj0EAwIwODEgMB4GA1UEAwwX\n'
                'QWxjaGVtIFRlc3QgQ29uc3RyYWluZWQxFDASBgNVBAoMC0FsY2hlbSBUZXN0MCAX\n'
                'DTIwMDEwMTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5WjASMRAwDgYDVQQDDAduYyBl\n'
                'eGNsMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEuYjLC5GtjAX52lLpiltzDos\n'
                'ICukjxvB1gJz6f5TUTAfDcQvPwd2SqvEEIZg8tNkyjML9O5tj+ccIHEgcMibXqNf\n'
                'MF0wGwYDVR0RBBQwEoIQYmFkLmV4YW1wbGUudGVzdDAdBgNVHQ4EFgQU0gkeOS9T\n'
                'upN/oLXdv/2aQAJVfLgwHwYDVR0jBBgwFoAU4rCqXHVY0Qw3OxLUP3oiNuksNZsw\n'
                'CgYIKoZIzj0EAwIDRwAwRAIgIJ7HgDCGRiPRIavcsuODier1iYybFHgzm9yOgDNm\n'
                '0q8CIGTUaRsj4XjPnnr5HLnYl8smjH6ZT0O5gxVUI6n9OgcK\n'
                '-----END CERTIFICATE-----\n',
 'nc-excl.key': '-----BEGIN PRIVATE KEY-----\n'
                'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgs+SXMeVuESyO/3Vo\n'
                '4dskB/Pk9wVbWlmxFfU+hN5DMU2hRANCAAQS5iMsLka2MBfnaUumKW3MOiwgK6SP\n'
                'G8HWAnPp/lNRMB8NxC8/B3ZKq8QQhmDy02TKMwv07m2P5xwgcSBwyJte\n'
                '-----END PRIVATE KEY-----\n',
 'nc-good.crt': '-----BEGIN CERTIFICATE-----\n'
                'MIIBpDCCAUugAwIBAgIIfNHi8ffYcqAwCgYIKoZIzj0EAwIwODEgMB4GA1UEAwwX\n'
                'QWxjaGVtIFRlc3QgQ29uc3RyYWluZWQxFDASBgNVBAoMC0FsY2hlbSBUZXN0MCAX\n'
                'DTIwMDEwMTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5WjASMRAwDgYDVQQDDAduYyBn\n'
                'b29kMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAECL8G+z17j2FurhGuMpw4ybsP\n'
                '/JmzQXcWEj2xJevKG7QKKVQ5cprVlk+MksP9YdQgajU79cQ9MtBqQlMgpdEgeKNj\n'
                'MGEwHwYDVR0RBBgwFoIOYS5leGFtcGxlLnRlc3SHBAoBAgMwHQYDVR0OBBYEFEQW\n'
                'TD9wCXyrn/e3b3zP7TF1xMRLMB8GA1UdIwQYMBaAFOKwqlx1WNEMNzsS1D96Ijbp\n'
                'LDWbMAoGCCqGSM49BAMCA0cAMEQCICQQ8S3HOV0bB1wlah7jfDUXmnG+sGlQz7h5\n'
                'gtGRaYlqAiBtQ63lvq3DRmPGD2oFpNIMTDuVaWiN1IdQIFn7VnJbUg==\n'
                '-----END CERTIFICATE-----\n',
 'nc-good.key': '-----BEGIN PRIVATE KEY-----\n'
                'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQghuDoNjYSxbBo7fXr\n'
                'q0xDQ4VAYxnhIbJ+9R51IlAfeFKhRANCAAQIvwb7PXuPYW6uEa4ynDjJuw/8mbNB\n'
                'dxYSPbEl68obtAopVDlymtWWT4ySw/1h1CBqNTv1xD0y0GpCUyCl0SB4\n'
                '-----END PRIVATE KEY-----\n',
 'nc.crt': '-----BEGIN CERTIFICATE-----\n'
           'MIICCTCCAa+gAwIBAgIIJocN78zUtN4wCgYIKoZIzj0EAwIwMTEZMBcGA1UEAwwQ\n'
           'QWxjaGVtIFRlc3QgUm9vdDEUMBIGA1UECgwLQWxjaGVtIFRlc3QwIBcNMjAwMTAx\n'
           'MDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMDgxIDAeBgNVBAMMF0FsY2hlbSBUZXN0\n'
           'IENvbnN0cmFpbmVkMRQwEgYDVQQKDAtBbGNoZW0gVGVzdDBZMBMGByqGSM49AgEG\n'
           'CCqGSM49AwEHA0IABBrifOjgAhDkIudzL2L4QeNkhy3jJh+AlwR1Brq/zV7URaFI\n'
           'jAE1q4fhC6HaJIJVrlV+u7fZ6HeG4KnH2WBbJ4ijgacwgaQwDwYDVR0TAQH/BAUw\n'
           'AwEB/zAOBgNVHQ8BAf8EBAMCAgQwQQYDVR0eAQH/BDcwNaAdMA+CDS5leGFtcGxl\n'
           'LnRlc3QwCocICgAAAP8AAAChFDASghBiYWQuZXhhbXBsZS50ZXN0MB0GA1UdDgQW\n'
           'BBTisKpcdVjRDDc7EtQ/eiI26Sw1mzAfBgNVHSMEGDAWgBRCjUpFxrruam//OYmO\n'
           'a+a0FScBmTAKBggqhkjOPQQDAgNIADBFAiEA84m8mry7oOmqrCJ+FTYRDD41Rg91\n'
           'zkzWLXOyMEHgvN8CIFEDyuBp6ZUerwuaAlFf9LvK5NyDKTLBwwhXgILcNckK\n'
           '-----END CERTIFICATE-----\n',
 'nosan.crt': '-----BEGIN CERTIFICATE-----\n'
              'MIIBjDCCATOgAwIBAgIIbXuwnGyW8ikwCgYIKoZIzj0EAwIwMTEZMBcGA1UEAwwQ\n'
              'QWxjaGVtIFRlc3QgUm9vdDEUMBIGA1UECgwLQWxjaGVtIFRlc3QwIBcNMjAwMTAx\n'
              'MDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMBQxEjAQBgNVBAMMCWxvY2FsaG9zdDBZ\n'
              'MBMGByqGSM49AgEGCCqGSM49AwEHA0IABKiDkFESA38weKVYsaSgyMflWwQj2vRH\n'
              'L8WQtzeDAQtu9jqvG35UgcI0n044dBDCwv8kxe37uMDlq8DjdpfN1AWjUDBOMAwG\n'
              'A1UdEwEB/wQCMAAwHQYDVR0OBBYEFEKId55fVfKJF+fmmTCtpOqJfD0qMB8GA1Ud\n'
              'IwQYMBaAFEKNSkXGuu5qb/85iY5r5rQVJwGZMAoGCCqGSM49BAMCA0cAMEQCIGO9\n'
              'M1CMxSKM9luRw9heCGHu83QwklMRvDLQycsssW9eAiBj705Cupoy7YzkjKSp2lpA\n'
              '3jcYO/DE2ogEXhIqk8pDFw==\n'
              '-----END CERTIFICATE-----\n',
 'nosan.key': '-----BEGIN PRIVATE KEY-----\n'
              'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgXq5nsstHNAZLEP0u\n'
              'c75E4X0D8ug28Qz4z2UeH6eIFQ6hRANCAASog5BREgN/MHilWLGkoMjH5VsEI9r0\n'
              'Ry/FkLc3gwELbvY6rxt+VIHCNJ9OOHQQwsL/JMXt+7jA5avA43aXzdQF\n'
              '-----END PRIVATE KEY-----\n',
 'notca.crt': '-----BEGIN CERTIFICATE-----\n'
              'MIIBszCCAVmgAwIBAgIJAI1aBVgdSMwHMAoGCCqGSM49BAMCMDExGTAXBgNVBAMM\n'
              'EEFsY2hlbSBUZXN0IFJvb3QxFDASBgNVBAoMC0FsY2hlbSBUZXN0MCAXDTIwMDEw\n'
              'MTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5WjApMREwDwYDVQQDDAhOb3QgQSBDQTEU\n'
              'MBIGA1UECgwLQWxjaGVtIFRlc3QwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAARk\n'
              'a9KRsOxtaVPtxap42MVd6kM+uHHooG7gwkjMGr/l7SqZ4v3phMXrBf2cwILNi9cp\n'
              'MkoaaWrNLgh/IpnggzySo2AwXjAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIH\n'
              'gDAdBgNVHQ4EFgQUCN0Eq4EZWaNZVJHosIoAkXsGhNEwHwYDVR0jBBgwFoAUQo1K\n'
              'Rca67mpv/zmJjmvmtBUnAZkwCgYIKoZIzj0EAwIDSAAwRQIgdA+LGVAdUmkNpDo0\n'
              'OTc9bMk08Gvh0INSCyTlStqxQt8CIQCN/wgkO7sjkBsEzrwm1uDraxeYAlWgbhQW\n'
              'KvrmESeqDw==\n'
              '-----END CERTIFICATE-----\n',
 'other.crt': '-----BEGIN CERTIFICATE-----\n'
              'MIIBvTCCAWSgAwIBAgIJALGKN4lHk395MAoGCCqGSM49BAMCMDExGTAXBgNVBAMM\n'
              'EEFsY2hlbSBUZXN0IFJvb3QxFDASBgNVBAoMC0FsY2hlbSBUZXN0MCAXDTIwMDEw\n'
              'MTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5WjAQMQ4wDAYDVQQDDAVvdGhlcjBZMBMG\n'
              'ByqGSM49AgEGCCqGSM49AwEHA0IABMuWSuBoRyMm/UM6Xi//ztCVoGsqb1U/jj0w\n'
              'w2zjknbR4U5jKkwM7bYftieVSgx8RxBs9cu3ETktcLSALiZHeGKjgYMwgYAwDAYD\n'
              'VR0TAQH/BAIwADATBgNVHSUEDDAKBggrBgEFBQcDATAbBgNVHREEFDASggpvdGhl\n'
              'ci50ZXN0hwR/AAACMB0GA1UdDgQWBBRA+0S4yueIlFTatWYrZKiQnkpyTjAfBgNV\n'
              'HSMEGDAWgBRCjUpFxrruam//OYmOa+a0FScBmTAKBggqhkjOPQQDAgNHADBEAiBy\n'
              'tEWFsFFpzrXIw7gzTh7226JE5ycQoUptToShYE/+YwIgRQYECI233UdT7Vo/jOdg\n'
              '0nKROXwqk8Ke3ckJ9ndvJqc=\n'
              '-----END CERTIFICATE-----\n',
 'other.key': '-----BEGIN PRIVATE KEY-----\n'
              'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgEIgbGObZFMVy0jzG\n'
              '5Z02RmRCtiEkwLcPl4tW0alCLI+hRANCAATLlkrgaEcjJv1DOl4v/87QlaBrKm9V\n'
              'P449MMNs45J20eFOYypMDO22H7YnlUoMfEcQbPXLtxE5LXC0gC4mR3hi\n'
              '-----END PRIVATE KEY-----\n',
 'root.crt': '-----BEGIN CERTIFICATE-----\n'
             'MIIBnTCCAUKgAwIBAgIIOrwgYKESdJMwCgYIKoZIzj0EAwIwMTEZMBcGA1UEAwwQ\n'
             'QWxjaGVtIFRlc3QgUm9vdDEUMBIGA1UECgwLQWxjaGVtIFRlc3QwIBcNMjAwMTAx\n'
             'MDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMDExGTAXBgNVBAMMEEFsY2hlbSBUZXN0\n'
             'IFJvb3QxFDASBgNVBAoMC0FsY2hlbSBUZXN0MFkwEwYHKoZIzj0CAQYIKoZIzj0D\n'
             'AQcDQgAENdF+cFi1YtZFVTgW32IUC5RrBngdUi3GbW3yox7wruOWp7G936+RFUjI\n'
             'en1IS8PQ+zqmQbilHB7MesHgsqxQS6NCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNV\n'
             'HQ8BAf8EBAMCAQYwHQYDVR0OBBYEFEKNSkXGuu5qb/85iY5r5rQVJwGZMAoGCCqG\n'
             'SM49BAMCA0kAMEYCIQC1hBGDLUAuQpln8+p8TH9Qt77o5cwGfIM3bFYJ+dZ4BQIh\n'
             'AKIKhOf6q0n3E5snsrcsSVcC/EnlZTG7OEm/c4erXDpW\n'
             '-----END CERTIFICATE-----\n',
 'root2.crt': '-----BEGIN CERTIFICATE-----\n'
              'MIIB5jCCAWugAwIBAgIIJfj38IrUiEEwCgYIKoZIzj0EAwMwNzEfMB0GA1UEAwwW\n'
              'QWxjaGVtIFRlc3QgT3RoZXIgUm9vdDEUMBIGA1UECgwLQWxjaGVtIFRlc3QwIBcN\n'
              'MjAwMTAxMDAwMDAwWhgPMjA5OTEyMzEyMzU5NTlaMDcxHzAdBgNVBAMMFkFsY2hl\n'
              'bSBUZXN0IE90aGVyIFJvb3QxFDASBgNVBAoMC0FsY2hlbSBUZXN0MHYwEAYHKoZI\n'
              'zj0CAQYFK4EEACIDYgAERz//RjI/0EWwZaP18jNf++7wBPbjLUGSZUaVZqbGdJ1d\n'
              '/YzP7k9HpDV6bjIkEYqGip1ODGtHCjKuoy38g9SJiMco4bWYo1IWkj/LABINhNTt\n'
              'EIzlarsQp4sgrkJQ6bPbo0IwQDAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQE\n'
              'AwIBBjAdBgNVHQ4EFgQUdukFwCwcy/+9X2WGgh9DtMzoN3IwCgYIKoZIzj0EAwMD\n'
              'aQAwZgIxAM7sBLxAzMMBTMB2Z5xIsR2TacWovfx+1a+ywPdFc0BJ4NHBndUEAjP6\n'
              'kdQ+J5vxYgIxAOy6nJawCQzOB5YM1DmsscCh5gj3Lm/Igu5VwzIcByehfH0mwX94\n'
              'Upxw+tFMe1RPRw==\n'
              '-----END CERTIFICATE-----\n',
 'self-ed.crt': '-----BEGIN CERTIFICATE-----\n'
                'MIIBejCCASygAwIBAgIILNb/RaQF6g0wBQYDK2VwMBcxFTATBgNVBAMMDHNlbGYg\n'
                'ZWQyNTUxOTAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowFzEVMBMG\n'
                'A1UEAwwMc2VsZiBlZDI1NTE5MCowBQYDK2VwAyEAoGwMDJ/y9EeIYM6+zwQVAN2F\n'
                'ZXt5UwEVg3Ffoyaw2NejgZMwgZAwDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMC\n'
                'BaAwEwYDVR0lBAwwCgYIKwYBBQUHAwEwPAYDVR0RBDUwM4IJbG9jYWxob3N0gg4q\n'
                'LmV4YW1wbGUudGVzdIcEfwAAAYcQAAAAAAAAAAAAAAAAAAAAATAdBgNVHQ4EFgQU\n'
                'Pzdlx3YJuM1PqG1eNJHSqt8MLoAwBQYDK2VwA0EAt0a2Vtdbg8vq9hqVr57jD86P\n'
                'oNpnLImBJF7SxR1p6V5AWRLPJ/LZmjz/P9tU1uhVG05IKsFPTeu9MzebNtJUBg==\n'
                '-----END CERTIFICATE-----\n',
 'self-ed.key': '-----BEGIN PRIVATE KEY-----\n'
                'MC4CAQAwBQYDK2VwBCIEIKmO7IUWPooWIH27y0xlEt2RX6P26Xbjkpp1K2lEynJc\n'
                '-----END PRIVATE KEY-----\n',
 'self-p256.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIIBtDCCAVqgAwIBAgIIEgbe6yREm9UwCgYIKoZIzj0EAwIwFDESMBAGA1UEAwwJ\n'
                  'c2VsZiBwMjU2MCAXDTIwMDEwMTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5WjAUMRIw\n'
                  'EAYDVQQDDAlzZWxmIHAyNTYwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAATGTqcN\n'
                  '/BvTlDyrtj4DnKdmS8GGOKpWARglt5Z0V1A5pZX2HTx4/EVbhG3SCQeWfixDHi/s\n'
                  'xlIRXeKCpnHJZqjto4GTMIGQMAwGA1UdEwEB/wQCMAAwDgYDVR0PAQH/BAQDAgWg\n'
                  'MBMGA1UdJQQMMAoGCCsGAQUFBwMBMDwGA1UdEQQ1MDOCCWxvY2FsaG9zdIIOKi5l\n'
                  'eGFtcGxlLnRlc3SHBH8AAAGHEAAAAAAAAAAAAAAAAAAAAAEwHQYDVR0OBBYEFNa4\n'
                  '98KP0dnrMzHMFpCyI01F1MOJMAoGCCqGSM49BAMCA0gAMEUCIDZURYY0ATQPCT/N\n'
                  'qTJICa/eplZPlSprj7igYUzjz3LcAiEA8DyTN8D9bWKEkiF/UnBb8lE2DTY4a33D\n'
                  'yyQO8Q8pmLc=\n'
                  '-----END CERTIFICATE-----\n',
 'self-p256.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgNt+0cEcPOkTbyRA4\n'
                  '1czUYhRAa5gw65tFEDhQd50ubb+hRANCAATGTqcN/BvTlDyrtj4DnKdmS8GGOKpW\n'
                  'ARglt5Z0V1A5pZX2HTx4/EVbhG3SCQeWfixDHi/sxlIRXeKCpnHJZqjt\n'
                  '-----END PRIVATE KEY-----\n',
 'self-p384.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIIB8jCCAXigAwIBAgIJAJ49ONhe2899MAoGCCqGSM49BAMDMBQxEjAQBgNVBAMM\n'
                  'CXNlbGYgcDM4NDAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowFDES\n'
                  'MBAGA1UEAwwJc2VsZiBwMzg0MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAEV2Lkm6F5\n'
                  'nKznxzJH4ke+KDUe757PhMgk/GtMwebPmXC1HZDOt0uOyE6bzM+9mRxIEtMRVAzZ\n'
                  'JD86EZ351A8V1/m7pDBRqlFIS+BfKwezynX/cNvqSPbdHpckI2G2h5kpo4GTMIGQ\n'
                  'MAwGA1UdEwEB/wQCMAAwDgYDVR0PAQH/BAQDAgWgMBMGA1UdJQQMMAoGCCsGAQUF\n'
                  'BwMBMDwGA1UdEQQ1MDOCCWxvY2FsaG9zdIIOKi5leGFtcGxlLnRlc3SHBH8AAAGH\n'
                  'EAAAAAAAAAAAAAAAAAAAAAEwHQYDVR0OBBYEFPlf4NOB31l4aYZgrtZpOA/TgtUk\n'
                  'MAoGCCqGSM49BAMDA2gAMGUCMQDX/5HM6j/E91MRZTW6SijFiPH4BfoQuIYy82Gn\n'
                  'wd6ZLGieFsDtJVjgf5HB1074oFwCMDPUU45gLICYOcmkVYweCElVw+Xo2+flJM1S\n'
                  'HGZtyRjAlN2fwQwTUTohh9JZ7Iqqnw==\n'
                  '-----END CERTIFICATE-----\n',
 'self-p384.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIG2AgEAMBAGByqGSM49AgEGBSuBBAAiBIGeMIGbAgEBBDBNHXQyLGd7zLN/aHQD\n'
                  'uFsOcf0tSHCbMiB8IKOqqyTvkTsk0KrvjYacwg//ivbXDkahZANiAARXYuSboXmc\n'
                  'rOfHMkfiR74oNR7vns+EyCT8a0zB5s+ZcLUdkM63S47ITpvMz72ZHEgS0xFUDNkk\n'
                  'PzoRnfnUDxXX+bukMFGqUUhL4F8rB7PKdf9w2+pI9t0elyQjYbaHmSk=\n'
                  '-----END PRIVATE KEY-----\n',
 'self-p521.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIICPTCCAZ6gAwIBAgIJAPev7O7rp4DYMAoGCCqGSM49BAMEMBQxEjAQBgNVBAMM\n'
                  'CXNlbGYgcDUyMTAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVowFDES\n'
                  'MBAGA1UEAwwJc2VsZiBwNTIxMIGbMBAGByqGSM49AgEGBSuBBAAjA4GGAAQBh0dX\n'
                  'IdDzGMjJf+m6B4BedMJF4Kidk3xAO4pING6DcS3U4GWPOj/M6PJQ2L7inxPzPFip\n'
                  '6mceu6Nxgwdf/LbuDbUA+YY3Uljk9NtavVlUxjctc6Ef4hKtZgsTcAGY5daaNASe\n'
                  'Iyq6Orbj20HMH2hcr7ZTZZFxrsnKWHKGILbjZ6Av/qKjgZMwgZAwDAYDVR0TAQH/\n'
                  'BAIwADAOBgNVHQ8BAf8EBAMCBaAwEwYDVR0lBAwwCgYIKwYBBQUHAwEwPAYDVR0R\n'
                  'BDUwM4IJbG9jYWxob3N0gg4qLmV4YW1wbGUudGVzdIcEfwAAAYcQAAAAAAAAAAAA\n'
                  'AAAAAAAAATAdBgNVHQ4EFgQU30LBFT0mZZdC+Fp5W+ctOlT3MgcwCgYIKoZIzj0E\n'
                  'AwQDgYwAMIGIAkIAhPqReI7J4ECOoM2RUjKc5qH7s9WbCnWCcfEjyEtAvoJuedCT\n'
                  '5INGUb3rdrUf4EPTxWbXVEkBjyQ0iwclHzwDYloCQgD8TFdwS0paNv1gq+I4claK\n'
                  'oo9GKb5gxYnLY2wj3r3V8JtLkgcjKLLuVXleWgo7mlmemzk1Aw7F3oa5UF7DYQRO\n'
                  'IA==\n'
                  '-----END CERTIFICATE-----\n',
 'self-p521.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIHuAgEAMBAGByqGSM49AgEGBSuBBAAjBIHWMIHTAgEBBEIApEOUxXQbNQicnk2R\n'
                  'eAuP6WcKchFTHlmZ539uKQ6Aufj1tSaFuH19otd6LGiz7kOL1sSaXmhburSFe2IH\n'
                  'zGfdV4ehgYkDgYYABAGHR1ch0PMYyMl/6boHgF50wkXgqJ2TfEA7ikg0boNxLdTg\n'
                  'ZY86P8zo8lDYvuKfE/M8WKnqZx67o3GDB1/8tu4NtQD5hjdSWOT021q9WVTGNy1z\n'
                  'oR/iEq1mCxNwAZjl1po0BJ4jKro6tuPbQcwfaFyvtlNlkXGuycpYcoYgtuNnoC/+\n'
                  'og==\n'
                  '-----END PRIVATE KEY-----\n',
 'self-pss.crt': '-----BEGIN CERTIFICATE-----\n'
                 'MIIEpjCCAtqgAwIBAgIIKOefgCGmZXYwQQYJKoZIhvcNAQEKMDSgDzANBglghkgB\n'
                 'ZQMEAgIFAKEcMBoGCSqGSIb3DQEBCDANBglghkgBZQMEAgIFAKIDAgEwMBMxETAP\n'
                 'BgNVBAMMCHNlbGYgcHNzMCAXDTIwMDEwMTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5\n'
                 'WjATMREwDwYDVQQDDAhzZWxmIHBzczCCAaIwDQYJKoZIhvcNAQEBBQADggGPADCC\n'
                 'AYoCggGBAKi6aWro6qc60xSOTJMwdHASpOBXvVdbv5p8DbAsZLeX2oNXBgMyKcZw\n'
                 'vr0gEaFJByFcq3UQ9Cgyff4Nt+oPsbphSIkGG4ee7ehO3xtVU4c+1E0B7inKXJbd\n'
                 'GM3Jfr+MCI06GoT7n7eVbIIhPQwvlKue8I8fxd6saIz9z4661sojgWioft3aloSl\n'
                 'dYCaZQtMhle4qbg+bSA1DOAvv2O8QaxDq5CKol/5Yph5bbcIYG4sR1Iqe3600WtB\n'
                 'yKVDWIFgdY/7/d1m2BTt5P9ycizD/V5U9rRNLxZtuWruDMrthdHRW/kV7kKV/LNb\n'
                 'eVWdpYmEOTEvdCXh/dXevZUboeG1m799iSHuutq2Aig2NwUFUVmnJjvej7wrW2rL\n'
                 'ZVH/Yb+/DDehiEjbXEr2oUE5mINi1iwffCBpexyRVnyxmjbvrrzCEkq9lFjkbb+P\n'
                 'FKwVYLhhTJVOq3N7VHZDRVjQTQAelcJQouMAvTBAx1HxrLF849vzirQU0OIeSKb7\n'
                 'dzPRRkqAZwIDAQABo4GTMIGQMAwGA1UdEwEB/wQCMAAwDgYDVR0PAQH/BAQDAgWg\n'
                 'MBMGA1UdJQQMMAoGCCsGAQUFBwMBMDwGA1UdEQQ1MDOCCWxvY2FsaG9zdIIOKi5l\n'
                 'eGFtcGxlLnRlc3SHBH8AAAGHEAAAAAAAAAAAAAAAAAAAAAEwHQYDVR0OBBYEFOA1\n'
                 'E1a1N08XgwOHfLNVPsn8Lw8FMEEGCSqGSIb3DQEBCjA0oA8wDQYJYIZIAWUDBAIC\n'
                 'BQChHDAaBgkqhkiG9w0BAQgwDQYJYIZIAWUDBAICBQCiAwIBMAOCAYEAXO2KdGOQ\n'
                 'ot4x4aoaZ4r3tKYCA0G7RZYP+LUmBnzGZkYJ0NlqAU2E1YCgKIbaFn2l/A6+pdYZ\n'
                 'HWGGs/+TkdTRz91V7sRrve1blPkOodM+ADXbXsD4qJ2S21Q3Bx7b8OsDbhwDwqDD\n'
                 '4ObraKdUEsW480HLoZVmM4usF1SXk+wT1Wjl3g8x6qXvnicA7tMjJO2CtmC4nf1K\n'
                 'hvbjdTUhAvkYVsJERWjeBqdailHEfZDVqRBz50kL+1llnIurquwq0aGMLR6tETmM\n'
                 'xyE++wHuoHsoe04JRL4F955xD7SBjBye5RQe/bLbmZVGtMEHdKCT77qprdBshLOX\n'
                 'kTMYb/TiqAYvfSHNfzQcEjlso7YQxMMcSZ6QW8dAXjtGMHhzn8qFbiQb+Px7EJZP\n'
                 'Ob8cdajztL+9+OhCh40Aykx5pzes2UIeEQgvfESupiiaAlPqcUgtKFPBVICRO2wW\n'
                 'gVoe3fL6z/Y6bda2O0PaSQ/aBL8upxtLGc2MtNVCDxiGKf1C5yLcAlAj\n'
                 '-----END CERTIFICATE-----\n',
 'self-pss.key': '-----BEGIN PRIVATE KEY-----\n'
                 'MIIG/gIBADANBgkqhkiG9w0BAQEFAASCBugwggbkAgEAAoIBgQCoumlq6OqnOtMU\n'
                 'jkyTMHRwEqTgV71XW7+afA2wLGS3l9qDVwYDMinGcL69IBGhSQchXKt1EPQoMn3+\n'
                 'DbfqD7G6YUiJBhuHnu3oTt8bVVOHPtRNAe4pylyW3RjNyX6/jAiNOhqE+5+3lWyC\n'
                 'IT0ML5SrnvCPH8XerGiM/c+OutbKI4FoqH7d2paEpXWAmmULTIZXuKm4Pm0gNQzg\n'
                 'L79jvEGsQ6uQiqJf+WKYeW23CGBuLEdSKnt+tNFrQcilQ1iBYHWP+/3dZtgU7eT/\n'
                 'cnIsw/1eVPa0TS8Wbblq7gzK7YXR0Vv5Fe5ClfyzW3lVnaWJhDkxL3Ql4f3V3r2V\n'
                 'G6HhtZu/fYkh7rratgIoNjcFBVFZpyY73o+8K1tqy2VR/2G/vww3oYhI21xK9qFB\n'
                 'OZiDYtYsH3wgaXsckVZ8sZo27668whJKvZRY5G2/jxSsFWC4YUyVTqtze1R2Q0VY\n'
                 '0E0AHpXCUKLjAL0wQMdR8ayxfOPb84q0FNDiHkim+3cz0UZKgGcCAwEAAQKCAYAR\n'
                 'usjR/ZiOqv08Jzm/q7NIhYUCt+WC9PacvpVXokqRCilhbLcKhe5i1j0MtX50wq43\n'
                 'oLu5iOcHBEs982YUd8K2sXtEPrqM1TPtmcAS6LPmvcDkOKQ0ivmQtrnhAd/KM+ZA\n'
                 'JM9dku01BsQIpoJ6MdO+9uwTNgT+QYKY8iCpwFNKmVGDVFVEbbAsTxCaS177wXZK\n'
                 'aHKZFCI2ZKyuMAY97i2+crvn69FlIVjtabEQLxam7QsvhJxGc6yfxyFU0E9QBPkZ\n'
                 'vcmV9lj0xSck7W4ePqbmVHQZAtlqkq1ur9ogvTe9dPaTInlMuGJPnWJbetCDy4Id\n'
                 '62WRDVTiPXljVoD+j2w3TcuiPLVy3ytuxqkdR682DUD2T6p7XDB+8UzF8RzyQtHg\n'
                 'gvXdtgS1lnMPZhA0F8kf+GGQ4bD81mw8K1O08HNkSaWGr8TQ3dU0Sq4F5SkI/uSu\n'
                 '8GIepPpkDvVhkp8hXa8aBQAIn4gn+8aOYsKo5ITHjpTGjb/gQrR31IXw26QD9uUC\n'
                 'gcEA3Q8eLTGHjWsStDY8jHCi3DadS/Up8p9J9zyyot7BEoM1fQjO532j44ieGGS2\n'
                 'lBjZ8p3pV6VmUJApKZwtzw7qo+wI2PGkzmR0czX9qgUK7ou+SvAGi9VLKWwfVRP2\n'
                 'qA1iwyGAInk9GGUgui3PZWwOjOl0V8BfAIp5ZmVEcoVnZ33A/JJ2kpJZynJtBkwS\n'
                 'i5qyixdUC/u8taVNJ+dH9bIGG+VGNsiwpGkH4R1McanumT2IBkSeEBVlQJAZKLTn\n'
                 'AIT7AoHBAMNlygstC90/zLI5NxtTLk8QtYIIfRXTThMVyPzneei/NuSx3MBGwfpE\n'
                 '8eujI+jCwNROPSaQ+sqt47zuksH8esTqODjEl9H4I2jT15bu7wNa76lio3hRT4CY\n'
                 'LdWX8qcjpsQm38W8FhrAnWYfq4VFfO3yHKD3s20IXdFf/HcH/xOBGrPidZM4G/H+\n'
                 'XWOvECAaIB1lRJfW/OurnVrS8wL/ApEFmH//cOD5Y5PMeYpoTIYv8rBlXM7te383\n'
                 'BBrZ31AehQKBwQCPoKP1rymoi7oiVt7uTLy0IdP/pzHzDuXK+qgCRILjmVamf5OX\n'
                 'Or3CN2Co7r7l6GOrTEhxBuk8TP5Bp9TnpIR1rwVsl0yCQSicNqcy0YXxyeAA5oUK\n'
                 'U7I7HqIY8Bihxdi2ecy8GVPFxucFsIABIL0vdvt9jGLtggswqXlYgy7VQhKiyDK8\n'
                 'NtSaQdBud/zQsdlxn92ez5gj2VwRIidSDrIDa+s76xdCK2/QJu4lJ8j7zcvUbr7Y\n'
                 'Kl6YHUgLd8ZjQwMCgcEAhTTxZmkRO4XxAFctED3GxjP36WvsCmMBSNWDLZaIb3lb\n'
                 '7NCsU5BpUTqLSj7vjhCm8JVd7trLfjzJktV5yzFaaL/cECdF8OifCynQQZ8l5j2q\n'
                 'QOlz0+RqtJoKNSDfVb5iRDrUNrMgxqAlLafNgI98uaJijgIPmfcoLkKnlGYpKJzN\n'
                 'HXD3AqQvuOvVss13ysrEtgWBm5n+1pMqNO62qIY8s60C58+2nkil7+5ntUmhUaGC\n'
                 'a2rOuGsB1BonfD6nlLEZAoHACJd33AhiWMT7oe7sm4NUGtN7PREkpRjUTrV87EsE\n'
                 '8vQ0ZL+Ri7CagNPMqfLJtB0Jn57aal2jGqqgA4g/aKZfVI3/bLx4OTl0J6aV/DaK\n'
                 'LDz39LuONctn2eymLjM9yaic1sqW/sw3cQjyHntigFK+/poPXtrPC2wwPch4fpqB\n'
                 'KgrKP1dkc8oE+4RVxre2c6c71pfUzFlX4AHR62vFCGrvGfLjkDRg6W1f/tefrXq/\n'
                 '1ACYDe9sWFCMPtul/uRCk7/S\n'
                 '-----END PRIVATE KEY-----\n',
 'self-rsa.crt': '-----BEGIN CERTIFICATE-----\n'
                 'MIIDPzCCAiegAwIBAgIJALnPyJ22jUgmMA0GCSqGSIb3DQEBCwUAMBMxETAPBgNV\n'
                 'BAMMCHNlbGYgcnNhMCAXDTIwMDEwMTAwMDAwMFoYDzIwOTkxMjMxMjM1OTU5WjAT\n'
                 'MREwDwYDVQQDDAhzZWxmIHJzYTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoC\n'
                 'ggEBALjUQe+mHcdN48xmSOaqwN4rrB8pvAGKpMfC1wnczojoKNj/NXFnEee884sY\n'
                 '6mf7DoNIORWBXcOLWsQz9y6BsPEodkDqQnjHbyWIUixniM4DGeRcw+gB5iQGi+YN\n'
                 'NmY2y8G/Q9/fdAtPeWR3Ba+62fNCMkxBW2wGFqoM3XnUQN1HFGCGrp+C8Ll0sSmQ\n'
                 '5pGE57yXG/qOPcA2RpSIg0I6SZKqUtuohE4W8aisszYzIOUvEc1w8+4CORPtDvq/\n'
                 '9c2KGi1/pSfXRUQvrgDgzAv87b3FYshR4oWkndyVS7TY+VZshB5Xorik1bLdQhon\n'
                 'bQe5Fx4q8wKolejv8vmryNjsvfkCAwEAAaOBkzCBkDAMBgNVHRMBAf8EAjAAMA4G\n'
                 'A1UdDwEB/wQEAwIFoDATBgNVHSUEDDAKBggrBgEFBQcDATA8BgNVHREENTAzggls\n'
                 'b2NhbGhvc3SCDiouZXhhbXBsZS50ZXN0hwR/AAABhxAAAAAAAAAAAAAAAAAAAAAB\n'
                 'MB0GA1UdDgQWBBS9l+t+vEApePxgctqheLni92cekjANBgkqhkiG9w0BAQsFAAOC\n'
                 'AQEAKonAD8+aQcdMZO2Qux3zu+R2+u+ZvkCDgUTLFX/zuAiKRgQkh4/Unx6zAtBl\n'
                 '2dOtMyCjwQWnBCbLo8kk4R4YzrQ35wuvWO1LoOsB0BQm43lHoDEuyLcYMpY1Q/1L\n'
                 'MEUmpjkTqsWE6NC3PWZfV98HwB1Es9lmHS/kNbRVlHsZGQ/GfuOSn0a0slfK3LaU\n'
                 'uTAoVy4EbsunJ6TYNPFLqlOqlulh9jLEYEFOk19Et5qBNzHBrBDsZYs4twG4Ohg7\n'
                 '4rrpcle54ruD9B3AkTiBpCx0hQEQTVszneiUgla/Osd7/QglVQu7N58jB5EvPmcp\n'
                 'q4pzMnS2fkY6RzvECsmNymKbVw==\n'
                 '-----END CERTIFICATE-----\n',
 'self-rsa.key': '-----BEGIN PRIVATE KEY-----\n'
                 'MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC41EHvph3HTePM\n'
                 'ZkjmqsDeK6wfKbwBiqTHwtcJ3M6I6CjY/zVxZxHnvPOLGOpn+w6DSDkVgV3Di1rE\n'
                 'M/cugbDxKHZA6kJ4x28liFIsZ4jOAxnkXMPoAeYkBovmDTZmNsvBv0Pf33QLT3lk\n'
                 'dwWvutnzQjJMQVtsBhaqDN151EDdRxRghq6fgvC5dLEpkOaRhOe8lxv6jj3ANkaU\n'
                 'iINCOkmSqlLbqIROFvGorLM2MyDlLxHNcPPuAjkT7Q76v/XNihotf6Un10VEL64A\n'
                 '4MwL/O29xWLIUeKFpJ3clUu02PlWbIQeV6K4pNWy3UIaJ20HuRceKvMCqJXo7/L5\n'
                 'q8jY7L35AgMBAAECggEAAWXKCfEUyZwkVE+CVHoywEtUYjTxMmODv+DcF0dARqcR\n'
                 'fgFM8MTKUtkecvjLa1Xp0oWK5vYdTvaGO7SInh96hp3EAYPLPafiDEDbqU4pNXaA\n'
                 'UCTGy9M2lAvXoGJqPOohHVnrvkRWXXYqi3DHDh3gBkNbIYLk6r2g9GGj115iLF0T\n'
                 'Ohod//kAO7wH3MmRpLJyNl87FjyoCilqPwzjZy6SXZyugq7i+YvbIPnOutptKo8r\n'
                 'ES99kKVK1HGfCdT+4lkNZJ4bLjbL6GRjaW72me4c1SjEpqayWB7zNEwjwp98R+1n\n'
                 'jIaJ6pdXC889Bk4W/3OI4z9ckjIPQZjRVpG3X6zfYQKBgQDs7yex4Tv8QM85X9C4\n'
                 'G6gcr+YQ/1BPH8fTGr1oodnkkKDv/EGLUNy/QDV4NcE4Cy0f54kv5PlOBLCPatwZ\n'
                 'WTHBROsEqDUlBtKy2CZ1VyNcnjLeIm9jPY9aRgN210cZbk23XBzlgDtpcaqItany\n'
                 '45VwCSAyclxv6msxqlHcH9RZaQKBgQDHs7ztsU23eb4hpgxdnQp/mwnSX75Sy8bq\n'
                 'bJYYuTV1boprsGlYQxyRSYQA4sE9xwnT8Q1txElBswRdX+avQKNKiFtABsQHLp3s\n'
                 'um6wXUvyf7WmTXDOJ3H/frkn1x1jhtZWo6K1B2Rows5t4RFAATraTP9LGDsmUwLt\n'
                 'gys6LwSeEQKBgHW3iMBPCI+W355A5aFjVE4UcrkFMLBvOMfA5FRE/c4asWsqqKIA\n'
                 'Jfz7eNVl177xhpTwY2+hUuAZYmOPExWhBCBjDmU88VKZJjvnOoxYI+CTVPCaqT7k\n'
                 'SgHvAS+dW9zduc0c/dpksJ/98l2D7JEZ05hbYFzQBu8vx9xgI9W7FrTpAoGBAJzy\n'
                 'g38DI6MYyPbE+17vNvsGq/dsS7XidRhz8prHpF4AXEU6RfCZ/e+pKVdQ3rJgpTau\n'
                 'cfFcnH5H5RxFbJU7ZZoEBEMTjihe2Lrd4nQ1PqT8/ZQPtKIwmgVEYNwQ0gYQSI+a\n'
                 '1xsTDjTPNVFh2x7EWK6MaO9pwcLi5qAnwGdf4G8hAoGBAIsDHjutU7HKu/ZwO1y+\n'
                 'azXFKqNlh7X1eNDQcPkXdtxluiB30FiA/Ob7iLSS5ab9tmAep2kumw/zMJCf3Xjb\n'
                 'G1Ddu/vx1zSqWWn4IT9hnLpd0fWfkQx2q3NktPloVS/CwKAPdiEdyt+RGCIF6uWZ\n'
                 'rRZA/mvK+hFrPOCsx88FgVt7\n'
                 '-----END PRIVATE KEY-----\n',
 'self-rsa4.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIIFRzCCAy+gAwIBAgIJAImineBzd+e3MA0GCSqGSIb3DQEBDQUAMBcxFTATBgNV\n'
                  'BAMMDHNlbGYgcnNhNDA5NjAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1\n'
                  'OVowFzEVMBMGA1UEAwwMc2VsZiByc2E0MDk2MIICIjANBgkqhkiG9w0BAQEFAAOC\n'
                  'Ag8AMIICCgKCAgEAuBEHsssL5k7Fu92RE/xa3Q35kRIZxKIdIRcjVLYM+x14z6ZE\n'
                  '2XjiyJRZSY+CQJhD1F1Mb+tT2xNdrvzkCPrDDTpQP+gei8QX52iWuGlWXOt0rScS\n'
                  'kg5HbtsdMVB4RacL4m+Dh8BztcLJ1HRkOWlGoegiB9aZUcqYsDjIQglt/jMh1VH3\n'
                  'VJJEyaWrGWQuGzbXXvtyoD/nRFcQI4X6e3/zKEWSC31hLfYp87RGrZUPn/DqDdWD\n'
                  'W4lQbrh843f3db/EfdSefERakR6AUM8/g4axpqSQ6mxfL5ZeuW1NdCxTioja+khp\n'
                  '6JLqUsnopfJapfjnpK7WkAgZMPLkNN0KdEUE4MDaTCyF+M12zR8GNUeFDYs3Szf5\n'
                  '3l5wjun4MwMqEaGXR/xbQMvwrhm+cLNwOAfGBgrUTDQhx2NozGeh1IZs4ioelqv2\n'
                  'cNmZuzEUpPRUnB5yANv3/brMMulfbsymIxUEQ8Yn07BTwDtpUP4xz7mjHR2X+4c/\n'
                  'U33Mbv7VZivjGpAcKm8Q+K0Y8cKYsEERfhMcS6xDrCJtIsmqorJSe0jt0+htjKMB\n'
                  'Z50jRDlZciiTkKxO65tsa9OH4QDqUlOuf7iS03pfwl9JDfEyL9TbJ+Ny4IbfFf5A\n'
                  'eUuja7XPk4ETzUs1zm9P2rCakRWUbv2J0AbWCZPLvy/1LH+/SEq/7dg1tFMCAwEA\n'
                  'AaOBkzCBkDAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIFoDATBgNVHSUEDDAK\n'
                  'BggrBgEFBQcDATA8BgNVHREENTAzgglsb2NhbGhvc3SCDiouZXhhbXBsZS50ZXN0\n'
                  'hwR/AAABhxAAAAAAAAAAAAAAAAAAAAABMB0GA1UdDgQWBBS5XewQJYHkADkGiAiD\n'
                  'R9FZxDAOMDANBgkqhkiG9w0BAQ0FAAOCAgEApMDiGYo1qhl0mSvIovAJdJ3bDSAX\n'
                  'Vm2z1MivBcyS7dAbp5Wg9UgpKzEF1weMZCxvHGjSm0AGW9pFeUZT+GaPA1LOR0Hv\n'
                  'jNA+242LDD50g3q+TMSdFOPSxAiArRAAy2z80YBmo69PdQK4VHIBNxq0J8crhaak\n'
                  'Bc9MD8t3uhAdMCz2Zvx6b/Nb5eoILcWfQ4UDchqE50hYymISrr+fEbmm4cAYyGLz\n'
                  'RTCmLz8y+3Sp1hp0LWGPOdrlXmzhbJLB0WAQg3xxO6gQL15XErexqQDOKYlsK9IH\n'
                  'dibSGIztaIdq3Fwaos9+5AG6THv4K0NG855ElaQ+nNVnCkBcgcFWzaIjVhThcNRm\n'
                  '6QTC5S4Z69sz89JX2F7FGlx2HxqsV5SWvAnpmZ5HavFb2Ie0O9TSj98XIV1HV5Ld\n'
                  'jNRMSMortCUa7DpTqaFUvJtgnp23f3pIlH2j4a1WGNMU5qekjk+XOOENaw9drg2j\n'
                  'MC3jcY8W8TzHbNjvgIWBR8Pn3Nv73H9AQ6WJ/vE9t+X9PEBkIHDIJB8WXLIVAjqH\n'
                  '8/9a0Ao6gw4OEAUTyJirLs+m3Peolf9D1aDftL2qFgfYREn7sXmAQak8QLICC9I1\n'
                  '8OFD+lWsvLfSbkA2Xg/twbcginIIm1dh/eJYkxdo0KOnliYLJW9amUwEqhM2z+QE\n'
                  'SiJBb7lEAy5lCKI=\n'
                  '-----END CERTIFICATE-----\n',
 'self-rsa4.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIIJQwIBADANBgkqhkiG9w0BAQEFAASCCS0wggkpAgEAAoICAQC4EQeyywvmTsW7\n'
                  '3ZET/FrdDfmREhnEoh0hFyNUtgz7HXjPpkTZeOLIlFlJj4JAmEPUXUxv61PbE12u\n'
                  '/OQI+sMNOlA/6B6LxBfnaJa4aVZc63StJxKSDkdu2x0xUHhFpwvib4OHwHO1wsnU\n'
                  'dGQ5aUah6CIH1plRypiwOMhCCW3+MyHVUfdUkkTJpasZZC4bNtde+3KgP+dEVxAj\n'
                  'hfp7f/MoRZILfWEt9inztEatlQ+f8OoN1YNbiVBuuHzjd/d1v8R91J58RFqRHoBQ\n'
                  'zz+DhrGmpJDqbF8vll65bU10LFOKiNr6SGnokupSyeil8lql+OekrtaQCBkw8uQ0\n'
                  '3Qp0RQTgwNpMLIX4zXbNHwY1R4UNizdLN/neXnCO6fgzAyoRoZdH/FtAy/CuGb5w\n'
                  's3A4B8YGCtRMNCHHY2jMZ6HUhmziKh6Wq/Zw2Zm7MRSk9FScHnIA2/f9uswy6V9u\n'
                  'zKYjFQRDxifTsFPAO2lQ/jHPuaMdHZf7hz9Tfcxu/tVmK+MakBwqbxD4rRjxwpiw\n'
                  'QRF+ExxLrEOsIm0iyaqislJ7SO3T6G2MowFnnSNEOVlyKJOQrE7rm2xr04fhAOpS\n'
                  'U65/uJLTel/CX0kN8TIv1Nsn43Lght8V/kB5S6Nrtc+TgRPNSzXOb0/asJqRFZRu\n'
                  '/YnQBtYJk8u/L/Usf79ISr/t2DW0UwIDAQABAoICAD9A7vXUzBqRoGbufdAx7SHB\n'
                  'Dy342+0UTtFTy7rtMunK13z4ZPmdDsYiIMrkK7059jlQ9JcTdkY3Uf7z/gNN9WCi\n'
                  '1PgZMwIR2asW6JCn9ltJONfWMQ4LJSYl21LalfJNtQpUCw3IJ5tjPIurkdOe53x1\n'
                  'MtihuR9/8VfBs6Pp7Kgp9ysBF28zMrtfGLzJjgShJIMKAvqp6zYzeyLSBGGTd0K0\n'
                  'IbucExzB1uneXlmBe5SZrD0jzhfTSNY7xQNAc0Q+Ke6Z9fq7XKo5IpxilC+FRqB/\n'
                  'NiOxKUbHtHahZrgREYZugF35K5gWgLsBktcQQXF+50/TG330on+NQLof6dtJ6qIi\n'
                  'gPYwq2yNQkpVc3c5cByJQ0wQpyFBms7BvbVHz/9uphUH8MIc2ZBxQ9RWhh3yr9dz\n'
                  'QgzSOhncNdLcK7XUr6xuBIUTFQNhp438dplmRtsXC+PPnxgnRHW2hg4K8HKwMExM\n'
                  'TucZzhFrwl5HW/lcncRcipZpc0QgBStJMpEqVfeQb2MZ/NUq+Hx0ymOHNNa4X0Gf\n'
                  'UdeuHITVkISLu+yhnuYUo2lVPryret/oghj80kxTXmge/Go1OlbeABY7Rj+03yjm\n'
                  'VvchS+JSCHggVDmlr/qmaNwR037nwRFa9nwem5W6PshPqTfug0/04+c34HeSoZPp\n'
                  '2xzDeW26vq3XyK+W4dBtAoIBAQDmHxluYOikEDUiUoW923CW06puwTTDSwhKrL2d\n'
                  '5Mf6JBKej9gAVmROgmRrLDErwYbgFOW+d0ANZgOhLtTJw1WjWwlODQA2Lo8PqDLE\n'
                  'cs2W5PMyG2nNgSia5deFeomf/j06qZjUBPSMsoqmYDQv0X3S3UxJ/GNNNHYoXc+x\n'
                  'a2+4uaDE6IcN+h1BveMRMnGaQnVtwgMvc5d0VUwAR/aIRWJDmAp5+2MyLgIKHxKG\n'
                  'FrkdM1ZRxDQcSx4c/eU7iuyIiIXRhZ6Yr+N8J5eaEjN4OgYfHwrc0fIGf0DFcJ+d\n'
                  'RUYZVEIJiwcAQqtXi4vN8gFiviMe6Z3fzFpevMVismwQhbn9AoIBAQDMxBFhHdwT\n'
                  'kROVIPt20uGIXZaonmodDAaYmxEH+q2c89iG3w50nYe6fO3dt+yXvSgLS58hxgNL\n'
                  'WjB7N2tU6SVACKgFZwK/LWidHJs8AIEvNpY8pMkwLL3xnCJdGOHis/wo9l4uT/96\n'
                  'UJvG6/zYBB1El3hpGgWs+/DJK2Wc9XdVUcyveQcfGUogAqUFWtdIrCoo2OPBomlr\n'
                  'UB63Wv9zxZYesXEIwfnSRXzMoCoTIWwDxPqOikrCaRXjP2tG9C5JsPNcXZweudDk\n'
                  'fCpWKfRhSqlIzy8366K/K84X+CkmBEdH1gzWsXH80TMnhufQkyigRbm2IoLP1g5U\n'
                  '87R3dRtBXxCPAoIBAQDh6jgaP7NEldDEEEXSPONMfyI7txuoejn6rZk9sEOO0+kf\n'
                  'l1HUCvxQgvw4ptri/Qv/YySlFwdf3/3COGqYZVbml1IMOQEzMAQst9CXQamJ8Ny8\n'
                  'HWOCZ8FISEqMdN81ne/YbnVl+DNpCULK0XmKVFz1LWJe5BNM0SsKuAZVRIcaz8oA\n'
                  'ZdNoqlocl2GbGW2jpokIJsbfx9gxUifZwsxJvewZNeNbG6unsLk53IVf9GDpROQC\n'
                  'Q99ww2IdzjhEez95TqYpKsenWE25LllL3YCAEF7AIMaWQNoc/MLG0qkwSbjm1uw5\n'
                  '2C4YWFtEB/BJT8OCf+2UxH7EHie+CA6ztTwYAGC1AoIBAGgQwXBk94MuORCSaZpz\n'
                  'BFIEllvt3qoSgYuvS1GN0gwxVXr+A9+6a8+YTF9haSmY5bAP57kHZIc4N+l3OeI2\n'
                  'd0r620Gbn6a/kio+7pno+76d9G6vpNwJ8SLIoiJEUhCgPmgnBaht2b41F2Zaau7x\n'
                  '8Fn6zSRFKFtI04+5sXO6wMIox2jqjnb8qFJqZam6CC2T6f1GdUHko8T5PBMdeTRC\n'
                  'V9ATiAnWY3u8+vcX8yoz0yx7QIeOuv3g4FHU2lV+JcQn3Ra1MHHhJ8vnWrDds6h6\n'
                  'hFxPh4TZCaY0whImeesrQ3q7y1yVZAQD4gaVply3XW9O4FozYd30wOXl0XLgnlBz\n'
                  '2vsCggEBAJ3v69wro2/QBSPz9gq3nVsXzqs6AKzV++NlncBNnQASaK8vl/aB2YVS\n'
                  'fXlfBYXptuzw5zdDQCAhDE+imtxENBJ8Q53leMM+CtA0ZVQBkYYl0G6jwZX3WDQS\n'
                  'kxSQBFIedD9UcmXlc0iZRZACcl/0NLjpOmKyAi3WEHlEycrtFFPwEDhimRqIwV7N\n'
                  'iGVpsks+IgAumqg10F5P25yzZg2z9Tgj4N/+rsQhyvoVVDuJ4w8UuStapB9fBb88\n'
                  'YhkJRFl3YJBXZuPCnj5fPP0h6ZkrlGaYnOYEHhoTHukSTlnz8c2L02IP1QOuKa+S\n'
                  'd8YawTpCjpXF4clNHO7bOqRJ97yfH+I=\n'
                  '-----END PRIVATE KEY-----\n',
 'self-sha1.crt': '-----BEGIN CERTIFICATE-----\n'
                  'MIIDQTCCAimgAwIBAgIJAIcuy5ZMzn0gMA0GCSqGSIb3DQEBBQUAMBQxEjAQBgNV\n'
                  'BAMMCXNlbGYgc2hhMTAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIzNTk1OVow\n'
                  'FDESMBAGA1UEAwwJc2VsZiBzaGExMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\n'
                  'CgKCAQEAwpjhF8XALQ8ooomGfMGbY+fVzO248ySb/XKc8yXWZho3W/7J+ymPw/6e\n'
                  'hltMWT4YzstfJmdgJH22Cir8RbDAyHyIuB8kDsdkDmf6C1ilwSOQIksfqB7eUUW+\n'
                  'OjvfFcZMA/aON3gGsufXWRDmcsdUPzIyl2RNaiUhZOLSW1fiISZ/8Ze+uBRdyV9x\n'
                  'iywZL/Oq88zMyPo1Q8uLJmj8OevnzIEx+z3OouDt7yTRNkhPMqKGITVNJ6DIHtoT\n'
                  'N4Y0gMxr/HAu6YaGEzebuzYgf/yeXErh0rJHo4hT3fcyTZzXw8OC0IVIrBy5+S03\n'
                  'Mf85D4afbrfftrV8PTA4GaOkEiGiFwIDAQABo4GTMIGQMAwGA1UdEwEB/wQCMAAw\n'
                  'DgYDVR0PAQH/BAQDAgWgMBMGA1UdJQQMMAoGCCsGAQUFBwMBMDwGA1UdEQQ1MDOC\n'
                  'CWxvY2FsaG9zdIIOKi5leGFtcGxlLnRlc3SHBH8AAAGHEAAAAAAAAAAAAAAAAAAA\n'
                  'AAEwHQYDVR0OBBYEFJWSkaMs6fBa+hHBfrx9O4Hxx5jgMA0GCSqGSIb3DQEBBQUA\n'
                  'A4IBAQALYIqTFxc99nMdubWeYQemzF/6c5pACkTGQInsLxUGLzZKQx3QT10MosFU\n'
                  'Swk58ZPZ6gFTP3zDsP1WOdaSdtz4Fm7pKK8y5NJJAOqIiW1iHZsS5y24dIPNeJlv\n'
                  'jfjul7d1VnZ4ZgZF557eWccTS9kiuWuycdT26Z019OrmVDTNW7qeqSTmsY1e3jZf\n'
                  '3CvYrbCujfOwPRa7q9W5m9d46h0eeTuXgxGgBvJoZc9eBv+T1SnpraCqeBjGxz/i\n'
                  '/juMGIpY2tjl0kb1ekWxv6l3roNu0dKX3aI8nSfLXlK+n43X9Xevp6+KLlaLHxuT\n'
                  'nnBtsQsjnocDqCwkEHivDmWVhRlr\n'
                  '-----END CERTIFICATE-----\n',
 'self-sha1.key': '-----BEGIN PRIVATE KEY-----\n'
                  'MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDCmOEXxcAtDyii\n'
                  'iYZ8wZtj59XM7bjzJJv9cpzzJdZmGjdb/sn7KY/D/p6GW0xZPhjOy18mZ2AkfbYK\n'
                  'KvxFsMDIfIi4HyQOx2QOZ/oLWKXBI5AiSx+oHt5RRb46O98VxkwD9o43eAay59dZ\n'
                  'EOZyx1Q/MjKXZE1qJSFk4tJbV+IhJn/xl764FF3JX3GLLBkv86rzzMzI+jVDy4sm\n'
                  'aPw56+fMgTH7Pc6i4O3vJNE2SE8yooYhNU0noMge2hM3hjSAzGv8cC7phoYTN5u7\n'
                  'NiB//J5cSuHSskejiFPd9zJNnNfDw4LQhUisHLn5LTcx/zkPhp9ut9+2tXw9MDgZ\n'
                  'o6QSIaIXAgMBAAECggEAKWpYHbMcn3pmb5FNaifaZnzk5+SARF86Q8qs1KLs6nYR\n'
                  '6iZj3myOCGycWIP9z9CDfx+RdJ7zu1B1+dwELODdZs36WxVlmy+cf+RpNxj6zgw/\n'
                  'lMzgQ+ut7SYmwkYTyJKXgxBqXCvTYSgukOoj4bHCoGCSm93hDAIzBUGw+3fMzLkB\n'
                  'y9iDnXb1rgPSzXfb+P9iQcq8CuvucxW3r+fIHkcAwKgliTauXc01nniSVjWmtdv2\n'
                  'tXuZBQeDlrVAxEZRl8xGNpCEmq6ZhzZ4vabWpGc4GSsxuev0KNBlgGjpbOCxSPsk\n'
                  'gxGJh44rEaELWxNrlQK9FpCr6C1YFeppy6ACxSScgQKBgQDqSMjdixqu4F3ao5/K\n'
                  '2pcb7Xv8BnvIzQW7HOb6GYZZOT2ylDURVYSjPsVsQoGcvbNbIDivDSguz5QYuGX1\n'
                  '/tubsS00hM71gmj9u50rAdFpf86E9cGzzBQUD2ovyW1teEwxJYvzqJ0r6cM0EhRV\n'
                  'lbF+u9P8S/JdGg2Jj1HOJu1L0QKBgQDUomDpup68scUnSgXbDikI33XuGHbDZ/CQ\n'
                  'IsXFOi6DWVKB8nI+zGCPfDUXmDopsU5gpOGgzuqs3u6fp00RGRGquf7dHYTB3h0Z\n'
                  'aF6DyT0cVVc8GWdAkwVGnqO8JsMDoQ+OMfKRHvYSpwPfhBQsOQmU0XjgZDSLN/CL\n'
                  'VjwiUrtRZwKBgEB3+t4L0zHgB7OMZwI5GG/U79MwLYvZ7wPINj8IGxIeUD39zoSQ\n'
                  'lckeEtFxk50ADoS63x48bpxC/qu2wkfo86FqJdhX22NvmViI8fzNqURwqPGpdr31\n'
                  'IGlMvJmdwgDno3+6p0JLWcSltNN1Ticm5ArNwM2iUHUSIDuENqyVxaKhAoGBAJ15\n'
                  'hHyVEWp93Z0zXRLWcd14YUZsJ8if+bFFj2J5rGjqhghnHeUUR478VfWbb7fg8ELy\n'
                  '2YbWt0Y/9EmZBaJcBpGCHhZz/hX2AWcHvLetGe0Z5vlDdwyD1axvYKO/sT3G0lZk\n'
                  '91gyrdsyhdPLZYU62LW2TOciTyerziHjQ7XHv6KRAoGBAOUvMbt79bqIS+0wDqxY\n'
                  'uCwQ0EGfvEgDHRvIJT6/sYQRCqHghd70mmrd267oFcPFl0ZEFdlDVBcR+DMtwk2J\n'
                  '78RVTj6HeXbcNg7TEizBsbR976HxIOhseoDy0gvmcXDpVsNRYijAkdkkVx8KXeI5\n'
                  'QRQaEDJHX6zFePQhjBmGShop\n'
                  '-----END PRIVATE KEY-----\n',
 'under-deep.crt': '-----BEGIN CERTIFICATE-----\n'
                   'MIICnjCCAYagAwIBAgIITXWnI6BYkWkwDQYJKoZIhvcNAQELBQAwGzEZMBcGA1UE\n'
                   'AwwQQWxjaGVtIFRlc3QgRGVlcDAgFw0yMDAxMDEwMDAwMDBaGA8yMDk5MTIzMTIz\n'
                   'NTk1OVowFTETMBEGA1UEAwwKdW5kZXIgZGVlcDBZMBMGByqGSM49AgEGCCqGSM49\n'
                   'AwEHA0IABC3o4pJn5E/KnAnQObTQrb/36kvw+cSFUiCYqg54DLHgWD46A0OcId7I\n'
                   'NqUhVT1HGcuGPkFLRqIw4+35khmmVP+jgbQwgbEwDAYDVR0TAQH/BAIwADAOBgNV\n'
                   'HQ8BAf8EBAMCBaAwEwYDVR0lBAwwCgYIKwYBBQUHAwEwPAYDVR0RBDUwM4IJbG9j\n'
                   'YWxob3N0gg4qLmV4YW1wbGUudGVzdIcEfwAAAYcQAAAAAAAAAAAAAAAAAAAAATAf\n'
                   'BgNVHSMEGDAWgBSu1d9jApV3wwfuIeSkhlaJ/TJ7nzAdBgNVHQ4EFgQUMMgk1EsH\n'
                   'B2EO2yFaoMZIpu/FSsowDQYJKoZIhvcNAQELBQADggEBAEdixZjkTpeuUx5t9NUB\n'
                   'y3Rx1AUn5MJ5axwgV/ud4SPnlN55ejIxF0L1/whI4GFB0VKxyBaWWIFb79c7bhIG\n'
                   'cnNZcaSw+/SXcaV0RKUEgfH8Q2z+BOKC+dEn2nyKbnzGMDp+k4E1LgsY08QUBPxR\n'
                   '44xJjT+oLPmAbY7k7Aqy+xsYepR2FTi4bkY7Cj5wVhZVhKRNy1WKSbr59kZ9K/ss\n'
                   'bqf4DiAZqUqJodoy395y1C/H/qDGZ6XjdfpmKSgMgjG6wwkGZU0p7E0pdu7ivKae\n'
                   '+7u3DdfovMpsBVuALWZDXdg7Iwo1s+vMbLzLjjF5HctzsBXkV/LDx1wqNWYUv0h6\n'
                   'TE0=\n'
                   '-----END CERTIFICATE-----\n',
 'under-deep.key': '-----BEGIN PRIVATE KEY-----\n'
                   'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPHCMFdhIC0ENuUJW\n'
                   'rG2W1qQJCujzzSM2hMY8yE6fS++hRANCAAQt6OKSZ+RPypwJ0Dm00K2/9+pL8PnE\n'
                   'hVIgmKoOeAyx4Fg+OgNDnCHeyDalIVU9RxnLhj5BS0aiMOPt+ZIZplT/\n'
                   '-----END PRIVATE KEY-----\n',
 'under-notca.crt': '-----BEGIN CERTIFICATE-----\n'
                    'MIIB7DCCAZKgAwIBAgIIYZ43Ce1i4LcwCgYIKoZIzj0EAwIwKTERMA8GA1UEAwwI\n'
                    'Tm90IEEgQ0ExFDASBgNVBAoMC0FsY2hlbSBUZXN0MCAXDTIwMDEwMTAwMDAwMFoY\n'
                    'DzIwOTkxMjMxMjM1OTU5WjAWMRQwEgYDVQQDDAt1bmRlciBub3RjYTBZMBMGByqG\n'
                    'SM49AgEGCCqGSM49AwEHA0IABAeVkBzitXTGSeB7x06nwNXt1KOabyJ45cvyA8x+\n'
                    'j0VZYEfqAtfoS1eWaMlA1Ownn95760j4FK4WBMiSliQIjDqjgbQwgbEwDAYDVR0T\n'
                    'AQH/BAIwADAOBgNVHQ8BAf8EBAMCBaAwEwYDVR0lBAwwCgYIKwYBBQUHAwEwPAYD\n'
                    'VR0RBDUwM4IJbG9jYWxob3N0gg4qLmV4YW1wbGUudGVzdIcEfwAAAYcQAAAAAAAA\n'
                    'AAAAAAAAAAAAATAfBgNVHSMEGDAWgBQI3QSrgRlZo1lUkeiwigCRewaE0TAdBgNV\n'
                    'HQ4EFgQUT6sYRWwsM23vHd907pLxlxDnOwowCgYIKoZIzj0EAwIDSAAwRQIgfIkn\n'
                    'Vsv8PagRi0+cC7JUXx4JEJYqUTs3fvYZmfEZthECIQDVnnWLyaY4PTuSJafDWEbk\n'
                    'FlByqg13y6VyVUyoClrpgA==\n'
                    '-----END CERTIFICATE-----\n',
 'under-notca.key': '-----BEGIN PRIVATE KEY-----\n'
                    'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPcQ52NRfo8PZlEBC\n'
                    't8i0mhmaNaGplilkoe6eWODwkvihRANCAAQHlZAc4rV0xknge8dOp8DV7dSjmm8i\n'
                    'eOXL8gPMfo9FWWBH6gLX6EtXlmjJQNTsJ5/ee+tI+BSuFgTIkpYkCIw6\n'
                    '-----END PRIVATE KEY-----\n'}
CHAINS={'chain-deep.pem': ['under-deep.crt', 'deep.crt', 'inter.crt'],
 'chain-ed.pem': ['leaf-ed.crt', 'inter.crt'],
 'chain-nc-bad.pem': ['nc-bad.crt', 'nc.crt'],
 'chain-nc-excl.pem': ['nc-excl.crt', 'nc.crt'],
 'chain-nc-good.pem': ['nc-good.crt', 'nc.crt'],
 'chain-notca.pem': ['under-notca.crt', 'notca.crt'],
 'chain-p256.pem': ['leaf-p256.crt', 'inter.crt'],
 'chain-p384.pem': ['leaf-p384.crt', 'inter.crt'],
 'chain-p521.pem': ['leaf-p521.crt', 'inter.crt'],
 'chain-rsa.pem': ['leaf-rsa.crt', 'inter.crt']}
BIG=[{'a': '73fcd3d68e1280fe',
  'b': 'f988bfbee235a44b',
  'bits': 61,
  'e': '17ef995d289f2aad',
  'k': 1,
  'm': 'ffffffffffffffc5',
  'name': 'k1',
  'wide': '82d88a9461aca4f2d2167d76cc08d755'},
 {'a': 'ef42b8ea79a6146185487448cca9a5a5f1d4e27af20a195a235a17df07129803',
  'b': '74d5a0c712497b4c199a24273cd5206d00bfff38e33ec77e6182952357802ff1',
  'bits': 253,
  'e': '64a1e250610b26eb2c7c4c8fadde8a838f7ff4b47d9aa3aa9321b4ce115bca15',
  'k': 4,
  'm': 'ffffffff00000001000000000000000000000000ffffffffffffffffffffffff',
  'name': 'p256',
  'wide': 'd9688f2551b462e0b9848191193352bf2d34963be96d02edee6094231ab2e73b0dfae4d9d9b5b43272b0337936bf41f21e48b26b52cf38809873b980857ff929'},
 {'a': 'a07a3e96619c5f667bb99bc4afb84befa94e30cbdb611e0fa6bd9146babe30f9',
  'b': 'e9e8fc0306ad6370af0b9792b1cd61dff69f873403b82484ca3e699b8679b5c2',
  'bits': 253,
  'e': 'e648447ab115adb6a80a472d3ca9341f93b7b13b9fa2eb399d8dfa9a7b1cefbf',
  'k': 4,
  'm': 'ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551',
  'name': 'n256',
  'wide': '0f4629467c38aa7ed2a3c04d0cd93960fda3f0f1387cdde3a28d333c6ecee27cddf4a45002b05c0ce96cffcdc7065526c3850b73bf652d40eccd3a73df0f8774'},
 {'a': '0a4d9facc32609a94b28c49a5c3ad0037aeed579a41023590cd8686faa765afabf42681791af27f009cdf77e4db44525',
  'b': 'd45843efe46a2e4ad76bf72e22710f6b7f9b8647dc8d63166cbdde8f63a946945749e620c4f8c41f5d2a1b25a82d8391',
  'bits': 381,
  'e': '3bc1f448df56dbaa0ee66cac7737a63b33b38e3162441ee4c7d752d39dd36646720b1b00807137d33e546c8b3f2fc075',
  'k': 6,
  'm': 'fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffeffffffff0000000000000000ffffffff',
  'name': 'p384',
  'wide': '8bfc0107273dc561608041bb4a6a16f0518374d23e3d41749e337c307e475c71345c0d45bbd4e0a47dfb29923f0d7217a1351769ad7abc14b938819c324ee5e3e18bfa6dc72ed43a9609674294f2689b48444e2e8f283de228fa84164179653f'},
 {'a': '9464184f7206a113bdea3d49816025e69fe97a255d0e6f6c50fb8cb41b82785c32dde198ece0fc248cea367a62e947696cc0a8369a4b8f9d2d2ef93be7abe5be2759f5712878a860d189bb7efc3de199de3fedfee98ca3bf2e36c8533605a64df1f77188c9472d5877c1b7547206ed7821fa101e433ae8947e870c308193c8d6cbc95b0427e4d558ddc5f594969f6e0291ceab9253390d7efe5e2d91bf419a9a2fc52ffe9ad170009d89a09084b4ce88f258f969ef8cfaa5a2b0e0bd05f6797dd616167c7f754b6d5d6dddbc60968e11717ea39c53ad07e6cb1fb869e6df1faa75da671d255890409b18b8a004cbc252c59d96c32e7de3681020f7105bcd7992',
  'b': '4040f488b048880dd77dabe6cf0599f9c8a21d7e7366059b5a676659cb0e9708a1765fad7efe5ac43bfe2158483f92a76a50e0ff8e71d54c4352801f25f45ac37cf17e004b6123c716a967ed63e910941aaccc1ac33a28520bdbe7a7dc7e76707f8b755ddec7108c34e993feeaccd676f419a8ae70110294f9260be515ffd9e7456b5014ee1089958927998cbe09e294552b89c83448daf84c048799e8481ade50ba4f6a25f8a0b649a9c15a24f5f54946432d1209ed252cec111e0d2f0b6fa3a3f17ceaaa4463b85eff59e7062230322399845079d375d0aab6e27259b3f1aa3ea8b0852dfcc78090135bc833a298bb80712d0f7527a34f843c531f085bee56',
  'bits': 2045,
  'e': '74181927b4addbaf91dc74f1f75c708349cce8ba0c79cf7b521a4ef613487a8fb11dd91f36cb1b072c8b45680559a0822c4c56361380071b37762d37cdea9da7a1f2d824a62de9b92933276362a7aacd8a33208b5f94e40f633bbbf9a16eb39f0e6923b1aea4277a0344da3240dbad446ea1687c43de0e61806d0ba4afe98ddbd6f8589f1998360e303b54db826932066fe1e8b01880af3fc6ec9a8b65f0bdb0d7416767f793564decee8e191c48fb3920878be5c3da44f0198315ffffdf7ddee109a868b5e80706147f06f3a3265c5e1b1c6209726b0beac66e527cdc7a2b19b4d443b6fc82c1b3b072e5f17470b7ef5f658693dbd53095c760c2a54aa31ca4',
  'k': 32,
  'm': '969008724392873ada2b1fc8930be6c934f40d483630871b50619e6f88f9a423f8c1ebe523b6438b0e5f6db1cd783274fb49fd5eb1ec171400cb989363332d0750eaf92a2abf4715f69c1b26edf6ca650fb1a0a57a68207439cc8fcf3b50ec810191af520efd7f2537761e968d3fe0308fb5ac5acf7bcccb4cb0ca6a5492ccac81da9b3b7c8e53d99b39ca5a070717d948728096b977a6852ea92abdaa7c98aaad93ba820ce0a7e09bb5cb1c465a4f530e1eb892dca2659d5caa663b7191aa35b15de681febb323890d181da410264e9054b9495d84c3e79f2234534f9e8a973377c36c09c37d74bc51149d0b6ea8a5c84383462b4840cc47b21ef2ecb49a2b1',
  'name': 'rsa2048',
  'wide': '428d660c3e791d94294a8fb2de9ce9b53c2d98369d69cc5f94ac73145d00d494c6b41259f44e17aa9a6169e2560f552571f450bd8bb21e6087ca06cde62657109f5020113f926842e4b5329e8eaa381f28360f16dfe1bb40c52f9a611006d4fc3bba8a8ac57e4af474dac8e45c829f029ee14282811d54edc8ed966672159f0c58df34be32b7d89657594497ec40149db84a7268af883196a527af04e14409583f4da3e42bec3049f55f7c4d5eec041b62cc63b097b5d7859342aab85183dfa7bb50d608f34248d343e26ffb421c63452cebd0352ba1051737b7db81e6487635d26fd8a7af4e5d89cc628a8e321bb774618e4f9c5e2a55ed3298dd08231f1ca625fee6ff0fc8ed687af8c986b91ff207b30de7b4f9a5c7fe93b5216561242b4fcce643727b95e49b2edd64e3e1427a819ae83b6f53cde6ee01cab6807ae7b1833e6a829551338aec3ac90a47f0fd11f53166f855cd927cab4716fa006b7687ff558e80e06b5f4b44620cd267fdcd8b909ce12305b7b45f273de26f322ac5d3792e5faf3cc49e877b6c595880251ccf70580692e4d140deea4bce3f4c38dd681cc06a84ef9c88854c7eb9a22dae49e498556b5ccc2881db3539394a7e6f63fe27ada25c8495cb419040ef14bb649b5a3e673f033d721895634b36c7e1720284ac80bf1b8b45941a0563ea096562f87f82c44b2a1e353249643c6997d10afd8f08'},
 {'a': '4854646f12c8f6412ec670f230665e8e5ffea65b7d406b8d44978325e64c10b57ebbd157ccacddd790b2303451fecb89d3a9ea3120ee6f5c0ffb61a4692ffdf9f1b8f7ddc1e75c4ed223a993d780fd8af4be88241a741def05e60c4962110e5046825d2f1df7e538163311e1cb90afc6b8b77601cf81a47c91634ee5791211954417ac8b8755b13e36a966ae0f5d3e52dafa6c5f0ec5a995f5e18e60063750a6960b9ec9f7526c31131c0d891a619bb1ab648e63b477f601db746066718fbb5911e47314e3b5c6ef314b7e1359f8a4340c69573c2835de10cc4705c4eb98cbfd06be0a64a8cb9f9445806b649b131666086d9131d643b7eb05a810a400d3cf02c4b9b0dcbb5e0e6a55a6d3e694d5f1822fb05e9b6db83d2c2323213c4ffce1156932cb9d89d832c7698401015272ce80060f410283aac7f0f034095760b5efe84e42a4abe1acc6ee11fdf5dedf5d62517ea43ae60c0eb5d4bb4c000def15496c036560ad9a7b2c5ae9f38fb9d8c87fc20876c47b984e9f1ae10f13192c17384c07fb39647b110308074e7d1d6121882f244f533b0735aca058135e42a91ee413aaca40a84903c862e487f92503e852708ff9b15d0a7da89166b7cbe71b9f18265217f174dcf5fee91866175721f3e165773767a569f1964686102d41eaac715dd65389119306805cdb5f43a86cc1d40f8e70d6c817d589ea70f38d10f41e07e1',
  'b': 'ad4887353fe0186c6fab30dfeefe8f4a5ef09ff2b6b74896fe53d83950d338e7281aeec2c941704fabb689e85ec746014bdd60cff75fb7bdd99c1608694a36909280d700f5317080baeecb359a08c614c366cca73d31fa91a3bbc9e9d02afc297d56b19761ab2fa5bae40a4f7f799cd5d56a9892e3df90de1f0e4a5cd6b82745d340207b53e46e4118f88c872152ba291103608a6d906b275d3281dd1d4ceff7a23ea3a97582bdbd6eb603d0a882d55a650da1d9d6576822ff707a53dd607fd4004db5fbc2735cdabb9d3863b7147e3a174b4c99df909cc918fdf9e9798a125745634a5df62aa9136203b00e886a86f510b79c3a766e464d9af1f6cb78488c8f78a4890fb1d73104ffabde2c1875dd671ede3041ae4472ca00ada53bf5025368bd7824316227d1bb8d95b465fd96a4dd9630b738e05a793b278a27cc68b7544229a53849cf298539f974fe759d1e4c6fe02ab851ccdd969b45b909c065dc603f76907fa6d87ba001f771f99a8bdc512f9eb6f826a3f0c4a79a0a0674973ad19f828ed45b6ab6c4543daed844ec067aa09cae7b3e5114b298809c08042e022bc063fe98dea3993126c3165c6e92a115d9f7a332a9f83e672efd049f9b086c2bb4a05f3c8d000cc207585c56b6c8fe78bc172e12b6500173f69971fd2ed3342253be0790106a394f6a72603c4114233adb7dd9a148b1b70dbf08caa6beca174ee4',
  'bits': 4093,
  'e': 'd5942bfdf79c1b305da3282826759292ac78aa4ae56552a35e4c07c8e30df08ea42e4f50468c28b5b59f0ff913ae6ad767de9bf8e9ae19f10aebcb74415e6dfe8f698f79da331e82e01e1c7a992310a9eae2827a7ac1b62dfe9020131c8a6b8f92c8b51878b5e2852581e098013a503bc2690e3dd1a12e0941bdc3a7667e7ba4d491c785fb4989aa149b7d8754d78ffbc4bd256b1b88d982edffce00f8f1dab289a1e341e4fa3879023f823dc3038e9441408687f2c6a2452a322e4aa69e239bf63b6e40189531253926a98b2c6af1cbc173f75847bd407eb71b31b2a88d104df6589cafb585f607a4a8a13b67411acbfd982b1f175344be57ddcbd70cff61c44cfbf04ab23499fcad203fe2bd9edbf67da55b608739c8b4ccd845d01fb22b4d3634e92576e919db791933935b57d08be31140bcb59408c157af790887ae4b2d5ab3fe4a721c038aade0c52c026e1397ca55acd1b735dd299d8f871253b85766987d04e346f7c88939997fdac5caaf554ad126abb6276131f61f7d34968d86144220ea5ce74f9b375476aaa9915f5a6433a534c85e831709460938dd6acdc0f5786b60e082439bab2e04d6163e5013d57b22cdb1c13d9344685059755b122aed125a89c996b01cd14beec23cf4283eaffa7675ef2700760446d1fba8fd82576f0a971439c3c5455043032f93ab006baafac9e6203b1ddc2b37a6210681381cc8',
  'k': 64,
  'm': 'aed4d8400f3e0739afbdc16e0b3fdcf5cbe577fa99705ef4c6acf65d9f5d307d49fd0a6048b0b1014f62f4937ffadedbd84866030a9794390ef6ac255025d8ea88ddba53ee6edb9a9b8ef508f585e2ac939aa1d35495edae650e31f2decdab5b3aa1afeec1e57e8a3a1af80483ededfce07e278a9f985a176857bb16511f98a95242d5589b607a4a9227d06d4f53091c7b319d00b61e5d44b6f8660bd27afab2f0523c96e1f9cc93b59088d6ff3e6c60df909823c4b7ad977a87099c72b5e11443689cab6915eab97d264a39e0ca3f1b80a8855daa3b427ae2b8e1256cb480bb98cecfca84d0dc560e0227549e1f5f7e4b121e9e27d011f773e768ffdca0d699899e2ca4b0f5956f20b42e017b9b06bdbbf0ccdd108cfdff570edfc4035d4df77b28b0dbc8fedcbb28ff11e97f0c08c96e27c6603957111168f53e07fc366481771dddb17b19660ed1008ecef3fbc821ac88abff2e0dec4ad6935e44983bbe813e871966964f687612d858eb45921c42a853582eb8558921dd478bf0929cd181c826a938ed8c4860d583408f7c6acd0e0d599f98671d5d8da211ebfc69b345042d42242677fcbff918e6e58ae9698f1b15f20fd7060931a9fa7d5b5a5a205b2638db5d65dc83501bc1d3cbf59c494cf9a95f1b28ba4dcbef0b0f66e84d66137b8626aeed3928be739c1df301d94278a370a1fb41d7a518daca594f2e6dafed2d',
  'name': 'rsa4096',
  'wide': 'ccdd89e4502a492de245cb0c19686a48281c5e6a2ffeb94d39033bbfd310495c914b792caf68dd954d2801f92f75d1196b5923772362861631d39ec73a3957fce1c25dc6de0f8a1e7d3ccf404122afd23857cf96bc7d0e366ae72d528d05ed21f4f079f16b8fb43b614b9e3e3e7bcc310850ae2c8fd3fe45acf632ac219b49796447645bf5663be66edaff56e2ef34b0eb6067462c76de4293fd22fc807d4add51300f4e72aac59730e35ab74a42c5371262e0e957da9201aa424502905de7041421b26df6bac1214be9a9f37934d91a06893b89823b83999ce11ee30134ce9a4f883b53f92f2e7eb6bed35e2159eadaae382865b722576124ab5f66c7901671ab52d170778d9580e8e1ff99d95349238208582401a0984fb7d223c5055571d1415cc01027c8643bdd2253589b4bee16ce4598d42e012e7115d6ffcfb9bc5db34ce28ed01399016be288efb755ccfbd2562f048c95b11c2edb9781c163d5a769f892653c59230ad4c7794542a4a415a3587d9485eaa8827495f74c42e9194915790b71ceaef49dbafa3230a6e10e04d67e2900071aa94c4d024ca79c049edd19da0ef6ccbc1e5d7e09501eb02ea23b39c0974d1b41d657cd1131c7ed885639ad16915f05ef25aa5153dfaa3d1bc662cbacccf3296ff76233cc8e66833799274551e4118b50feb2537d0a1b4d0e9e085ce7d33d46e7e5d72ffdbdc5089efe361369ac1e2e7a42b10e008e8a7b61c6936ead1c148d530adbc138db7df63b26f0c8396d824501ce27d8776a362800dfdb107fec880544f450e4dfb1248519900a0617118d7abafd9ad4cec0437f9f5ec4086a3301293f6b7462764d6209cd07e8639e3cb9c214737322de42b62fc5a67f6a2389918e67f227008b44687836e00e780884f4fa352a3c6172d59517041119fee021d4e9174d949df85ca834ca41f887d8748e06d1b1fe8100f44db7446c44c578c1b0cb3f62e5db28beb86155b728fc95cc3eb57b87690676f5e8540a8e8fc7d62351e51709d7edc39c366727bc34810890e2491628d9904c3393f8e806b0c6a861bb6f44056001c04fa46125dc4fc11a3d3da662efbce4e16b40273bbc60880522d667974678594aacb08742e7b5beedf33e8ca315a7de5f5fe4a099da5e4fe61e38b22b08f2464e0e31bcbf003dba2c510ba4ac67341edec9eb5098e2effb6db11b0c3c6ac37df55bf5ee589036ca1b2da00173a8c305e3dd3d5cabe5a49d3258a31677711a46e2ebeaa36f5d77fdb8e2b11d772402e8b2a988bee727c973d8b5c5b2cca784179505c53d28d41bddbf68ed15d99dc905f3a4831a8e722699cfca1abf1a2e43362617143ec3c156473ef87b9357d9b1c38d7e2ef2893e630a353802444dd79fb679179b2fbff050bf78c94c8c31ef7a1b2d811696cee2b6d6c37f27b494c2ba401f1d3f555821e6aa'}]
GCM=[{'aad': '',
  'ciphertext': '',
  'key': '00000000000000000000000000000000',
  'nonce': '000000000000000000000000',
  'plaintext': '',
  'source': 'McGrew-Viega / SP 800-38D test case 1',
  'tag': '58e2fccefa7e3061367f1d57a4e7455a'},
 {'aad': '',
  'ciphertext': '0388dace60b6a392f328c2b971b2fe78',
  'key': '00000000000000000000000000000000',
  'nonce': '000000000000000000000000',
  'plaintext': '00000000000000000000000000000000',
  'source': 'McGrew-Viega / SP 800-38D test case 2',
  'tag': 'ab6e47d42cec13bdf53a67b21257bddf'},
 {'aad': '',
  'ciphertext': '42831ec2217774244b7221b784d0d49ce3aa212f2c02a4e035c17e2329aca12e21d514b25466931c7d8f6a5aac84aa051ba30b396a0aac973d58e091473f5985',
  'key': 'feffe9928665731c6d6a8f9467308308',
  'nonce': 'cafebabefacedbaddecaf888',
  'plaintext': 'd9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a721c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255',
  'source': 'McGrew-Viega / SP 800-38D test case 3',
  'tag': '4d5c2af327cd64a62cf35abd2ba6fab4'},
 {'aad': 'feedfacedeadbeeffeedfacedeadbeefabaddad2',
  'ciphertext': '42831ec2217774244b7221b784d0d49ce3aa212f2c02a4e035c17e2329aca12e21d514b25466931c7d8f6a5aac84aa051ba30b396a0aac973d58e091',
  'key': 'feffe9928665731c6d6a8f9467308308',
  'nonce': 'cafebabefacedbaddecaf888',
  'plaintext': 'd9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a721c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39',
  'source': 'McGrew-Viega / SP 800-38D test case 4',
  'tag': '5bc94fbc3221a5db94fae95ae7121a47'},
 {'aad': '',
  'ciphertext': '',
  'key': '0000000000000000000000000000000000000000000000000000000000000000',
  'nonce': '000000000000000000000000',
  'plaintext': '',
  'source': 'McGrew-Viega / SP 800-38D test case 13',
  'tag': '530f8afbc74536b9a963b4f1c4cb738b'},
 {'aad': '',
  'ciphertext': 'cea7403d4d606b6e074ec5d3baf39d18',
  'key': '0000000000000000000000000000000000000000000000000000000000000000',
  'nonce': '000000000000000000000000',
  'plaintext': '00000000000000000000000000000000',
  'source': 'McGrew-Viega / SP 800-38D test case 14',
  'tag': 'd0d1c8a799996bf0265b98b5d48ab919'},
 {'aad': '',
  'ciphertext': '522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662898015ad',
  'key': 'feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308',
  'nonce': 'cafebabefacedbaddecaf888',
  'plaintext': 'd9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a721c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255',
  'source': 'McGrew-Viega / SP 800-38D test case 15',
  'tag': 'b094dac5d93471bdec1a502270e3cc6c'},
 {'aad': 'feedfacedeadbeeffeedfacedeadbeefabaddad2',
  'ciphertext': '522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662',
  'key': 'feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308',
  'nonce': 'cafebabefacedbaddecaf888',
  'plaintext': 'd9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a721c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39',
  'source': 'McGrew-Viega / SP 800-38D test case 16',
  'tag': '76fc6ece0f4e1768cddf8853bb2d551b'}]
CHACHA=[{'aad': '50515253c0c1c2c3c4c5c6c7',
  'ciphertext': 'd31a8d34648e60db7b86afbc53ef7ec2a4aded51296e08fea9e2b5a736ee62d63dbea45e8ca9671282fafb69da92728b1a71de0a9e060b2905d6a5b67ecd3b3692ddbd7f2d778b8c9803aee328091b58fab324e4fad675945585808b4831d7bc3ff4def08e4b7a9de576d26586cec64b6116',
  'key': '808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f',
  'nonce': '070000004041424344454647',
  'plaintext': '4c616469657320616e642047656e746c656d656e206f662074686520636c617373206f66202739393a204966204920636f756c64206f6666657220796f75206f6e6c79206f6e652074697020666f7220746865206675747572652c2073756e73637265656e20776f756c642062652069742e',
  'source': 'RFC 8439 2.8.2',
  'tag': '1ae10b594f09e26a7e902ecbd0600691'},
 {'aad': 'f33388860000000000004e91',
  'ciphertext': '64a0861575861af460f062c79be643bd5e805cfd345cf389f108670ac76c8cb24c6cfc18755d43eea09ee94e382d26b0bdb7b73c321b0100d4f03b7f355894cf332f830e710b97ce98c8a84abd0b948114ad176e008d33bd60f982b1ff37c8559797a06ef4f0ef61c186324e2b3506383606907b6a7c02b0f9f6157b53c867e4b9166c767b804d46a59b5216cde7a4e99040c5a40433225ee282a1b0a06c523eaf4534d7f83fa1155b0047718cbc546a0d072b04b3564eea1b422273f548271a0bb2316053fa76991955ebd63159434ecebb4e466dae5a1073a6727627097a1049e617d91d361094fa68f0ff77987130305beaba2eda04df997b714d6c6f2c29a6ad5cb4022b02709b',
  'key': '1c9240a5eb55d38af333888604f6b5f0473917c1402b80099dca5cbc207075c0',
  'nonce': '000000000102030405060708',
  'plaintext': '496e7465726e65742d4472616674732061726520647261667420646f63756d656e74732076616c696420666f722061206d6178696d756d206f6620736978206d6f6e74687320616e64206d617920626520757064617465642c207265706c616365642c206f72206f62736f6c65746564206279206f7468657220646f63756d656e747320617420616e792074696d652e20497420697320696e617070726f70726961746520746f2075736520496e7465726e65742d447261667473206173207265666572656e6365206d6174657269616c206f7220746f2063697465207468656d206f74686572207468616e206173202fe2809c776f726b20696e2070726f67726573732e2fe2809d',
  'source': 'RFC 8439 A.5',
  'tag': 'eead9d67890cbb22392336fea1851f38'},
 {'aad': '',
  'ciphertext': '',
  'key': '0000000000000000000000000000000000000000000000000000000000000000',
  'nonce': '000000000000000000000000',
  'plaintext': '',
  'source': 'empty',
  'tag': '4eb972c9a8fb3a1b382bb4d36f5ffad1'}]
CBC=[{'ciphertext': '7649abac8119b246cee98e9b12e9197d5086cb9b507219ee95db113a917678b273bed6b8e3c1743b7116e69e222295163ff1caa1681fac09120eca307586e1a7',
  'iv': '000102030405060708090a0b0c0d0e0f',
  'key': '2b7e151628aed2a6abf7158809cf4f3c',
  'plaintext': '6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710',
  'source': 'SP 800-38A F.2.1/F.2.2 CBC-AES128'},
 {'ciphertext': 'f58c4c04d6e5f1ba779eabfb5f7bfbd69cfc4e967edb808d679f777bc6702c7d39f23369a9d9bacfa530e26304231461b2eb05e2c39be9fcda6c19078c6a9d1b',
  'iv': '000102030405060708090a0b0c0d0e0f',
  'key': '603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4',
  'plaintext': '6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710',
  'source': 'SP 800-38A F.2.5/F.2.6 CBC-AES256'},
 {'ciphertext': '66e94bd4ef8a2c3b884cfa59ca342b2e',
  'iv': '00000000000000000000000000000000',
  'key': '00000000000000000000000000000000',
  'plaintext': '00000000000000000000000000000000',
  'source': 'one block, AES-128, zero key and iv'},
 {'ciphertext': '',
  'iv': '00000000000000000000000000000000',
  'key': '1111111111111111111111111111111111111111111111111111111111111111',
  'plaintext': '',
  'source': 'empty, AES-256'}]
GENERATED_BY='#!/bin/bash\n# One-time generation of the test certificates frozen into harness/tls.py.\nset -e\nNB=20200101000000Z; NA=20991231235959Z\nkey(){ # name type\n  case $2 in\n    rsa) openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out $1.key 2>/dev/null;;\n    rsa3) openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out $1.key 2>/dev/null;;\n    rsa4) openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out $1.key 2>/dev/null;;\n    p256) openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:prime256v1 -out $1.key;;\n    p384) openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:secp384r1 -out $1.key;;\n    p521) openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:secp521r1 -out $1.key;;\n    ed) openssl genpkey -algorithm ED25519 -out $1.key;;\n  esac\n}\nca(){ # name type issuer(or self) subject ext-section digest-opts [notBefore notAfter]\n  key $1 $2\n  openssl req -new -key $1.key -subj "$4" -out $1.csr\n  if [ "$3" = self ]; then signer="-selfsign -keyfile $1.key"; else signer="-cert $3.crt -keyfile $3.key"; fi\n  openssl rand -hex 8 > serial; : > index.txt\n  openssl ca -batch -config ca.cnf $signer -in $1.csr -startdate ${7:-$NB} -enddate ${8:-$NA} -extfile ext.cnf -extensions $5 $6 -notext -out $1.crt 2>ca.err || { cat ca.err; exit 1; }\n  rm $1.csr\n}\nmkdir -p newc\ncat > ca.cnf <<\'X\'\n[ca]\ndefault_ca=d\n[d]\ndatabase=index.txt\nnew_certs_dir=newc\nserial=serial\ndefault_md=default\npolicy=pol\nunique_subject=no\nemail_in_dn=no\n[pol]\ncommonName=supplied\norganizationName=optional\nX\ncat > ext.cnf <<\'X\'\n[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\n[ca0]\nbasicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n[canc]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign\nnameConstraints=critical,permitted;DNS:.example.test,excluded;DNS:bad.example.test,permitted;IP:10.0.0.0/255.0.0.0\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n[notca]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n[leaf]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost,DNS:*.example.test,IP:127.0.0.1,IP:::1\nauthorityKeyIdentifier=keyid\n[other]\nbasicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:other.test,IP:127.0.0.2\n[nosan]\nbasicConstraints=critical,CA:FALSE\n[clientonly]\nbasicConstraints=critical,CA:FALSE\nextendedKeyUsage=clientAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n[critical]\nbasicConstraints=critical,CA:FALSE\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n1.2.3.4.5.6=critical,ASN1:UTF8String:x\n[ncgood]\nsubjectAltName=DNS:a.example.test,IP:10.1.2.3\n[ncbad]\nsubjectAltName=DNS:localhost\n[ncexcl]\nsubjectAltName=DNS:bad.example.test\nX\nca root p256 self "/O=Alchem Test/CN=Alchem Test Root" ca "-md sha256"\nca inter rsa root "/O=Alchem Test/CN=Alchem Test Intermediate" ca0 "-md sha256"\nfor t in rsa p256 p384 p521 ed; do ca leaf-$t $t inter "/CN=leaf $t" leaf "-md sha256"; cat leaf-$t.crt inter.crt > chain-$t.pem; done\n# one self-signed certificate per signature algorithm\nca self-rsa rsa self "/CN=self rsa" leaf "-md sha256"\nca self-rsa4 rsa4 self "/CN=self rsa4096" leaf "-md sha512"\nca self-pss rsa3 self "/CN=self pss" leaf "-md sha384 -sigopt rsa_padding_mode:pss -sigopt rsa_pss_saltlen:digest -sigopt rsa_mgf1_md:sha384"\nca self-p256 p256 self "/CN=self p256" leaf "-md sha256"\nca self-p384 p384 self "/CN=self p384" leaf "-md sha384"\nca self-p521 p521 self "/CN=self p521" leaf "-md sha512"\nca self-ed ed self "/CN=self ed25519" leaf ""\nca self-sha1 rsa self "/CN=self sha1" leaf "-md sha1"\n# what must fail\nca expired p256 root "/CN=expired" leaf "-md sha256" 20200101000000Z 20210101000000Z\nca future p256 root "/CN=future" leaf "-md sha256" 20980101000000Z 20991231235959Z\nca other p256 root "/CN=other" other "-md sha256"\nca nosan p256 root "/CN=localhost" nosan "-md sha256"\nca clientonly p256 root "/CN=clientonly" clientonly "-md sha256"\nca critical p256 root "/CN=critical" critical "-md sha256"\nca notca p256 root "/O=Alchem Test/CN=Not A CA" notca "-md sha256"\nca under-notca p256 notca "/CN=under notca" leaf "-md sha256"; cat under-notca.crt notca.crt > chain-notca.pem\nca deep rsa inter "/CN=Alchem Test Deep" ca "-md sha256"\nca under-deep p256 deep "/CN=under deep" leaf "-md sha256"; cat under-deep.crt deep.crt inter.crt > chain-deep.pem\nca nc p256 root "/O=Alchem Test/CN=Alchem Test Constrained" canc "-md sha256"\nca nc-good p256 nc "/CN=nc good" ncgood "-md sha256"; cat nc-good.crt nc.crt > chain-nc-good.pem\nca nc-bad p256 nc "/CN=nc bad" ncbad "-md sha256"; cat nc-bad.crt nc.crt > chain-nc-bad.pem\nca nc-excl p256 nc "/CN=nc excl" ncexcl "-md sha256"; cat nc-excl.crt nc.crt > chain-nc-excl.pem\nca root2 p384 self "/O=Alchem Test/CN=Alchem Test Other Root" ca "-md sha384"\n# key forms: PKCS#1 and SEC1 beside PKCS#8\nopenssl rsa -in leaf-rsa.key -traditional -out leaf-rsa.pkcs1.key 2>/dev/null\nopenssl ec -in leaf-p256.key -out leaf-p256.sec1.key 2>/dev/null\nrm -rf ext.cnf ca.cnf newc index.txt* serial* ca.err\nls | wc -l\n'
