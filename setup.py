import setuptools
setuptools.setup(
     name='onenote_export',  
     version='0.1',
     entry_points={
         'console_scripts': ['onenote_export=onenote_export:main'],
     },
     author='Daniel Mouritzen',
     author_email='dmrtzn@gmail.com',
     description='Export OneNote as HTML',
     long_description=open('README.md', 'r').read(),
     long_description_content_type='text/markdown',
     url='https://github.com/danmou/onenote_export',
     packages=setuptools.find_packages(
         include=['onenote_export', 'onenote_export.*'],
     ),
     classifiers=[
         'Programming Language :: Python :: 3',
         'License :: OSI Approved :: MIT License',
         'Operating System :: OS Independent',
     ],
     install_requires=[
         'click', 'msal', 'pathvalidate', 'requests_oauthlib',
    ],
 )
