from os import path
from setuptools import setup

def readfile(filepath):
    with open(filepath,'r') as file:
        file_text = file.read()
    return file_text

project_dir = path.dirname(path.abspath(__file__))
README = readfile(f'{project_dir}\\README.md')
requires = readfile(f'{project_dir}\\requirements')

setup(
    name='spotify-to-mp3',
    version='1.0.0',
    description='spotify to utube to mp3',
    long_description=README,
    url='https://github.com/animeprofilepicture/spotify-to-utube-to-mp3',
    install_requires=requires,
    entry_points={
        'console_scripts': ['playlist_to_mp3s=spotify_to_mp3.playlist_to_mp3_folder:playlist_to_mp3_clt']
    }
)