# BALA Bot V2 Hardening

This directory contains the isolated BALA V2 decision gate.

## Core rule

**7/10 or higher = eligible for entry. Below 7/10 = NO TRADE.**

The engine is intentionally broker-agnostic. It does not place orders or contain credentials.

## Safety gates

- minimum 1:1.5 planned R:R
- 15m/5m conflict rejection
- chop rejection
- high-impact-news rejection
- duplicate-signal rejection
- daily loss limit
- consecutive-loss pause
- maximum open-position limit
- PAPER_ONLY configuration

## Required production integration

The existing market adapter must feed computed 15m/5m/1m features into `evaluate_signal()`. Only an approved result should reach the existing paper-order layer.

Before any live deployment, run a statistically meaningful paper-trading sample and verify net P&L after brokerage/slippage, profit factor, drawdown and execution quality.
