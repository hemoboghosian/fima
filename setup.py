from setuptools import setup, find_packages

setup(
    name="fima",
    version="0.1.0",
    author="Hemo Boghosian",
    author_email="HemoBoghosian@gmail.com",
    description="fima – A Python package for scraping and analyzing Iran’s financial market data. "
                "It currently supports bonds and options, with tools for calculating BSM prices, "
                "greeks, and implied volatility. Future versions will expand to include other instruments such as "
                "commodities and more.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/hemoboghosian/fima",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["pandas", "requests", "jdatetime", "numpy", "scipy", "bs4", "selenium", "mibian", "lxml"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    license="MIT",
)
