from setuptools import setup, find_packages

setup(
    name="seed-pitcher",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[line.strip() for line in open("requirements.txt").readlines()],
    entry_points={
        "console_scripts": [
            "seedpitcher=seed_pitcher.main:app",
        ],
    },
    python_requires=">=3.10",
)
