from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Numeric, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class UserAccount(Base):
    __tablename__ = "user_account"
    
    user_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)  # stakeholder, approver, admin
    email = Column(String(100), nullable=False)
    
    requests = relationship("MigrationRequest", back_populates="submitter")
    decisions = relationship("ApprovalDecision", back_populates="approver")

class MigrationRequest(Base):
    __tablename__ = "migration_request"
    
    request_id = Column(String(50), primary_key=True)
    submitted_by = Column(String(50), ForeignKey("user_account.user_id"), nullable=False)
    prompt = Column(Text, nullable=False)
    project_json_ref = Column(String(255), nullable=False)  # path/ref to stored legacy config
    submitted_at = Column(DateTime, default=datetime.utcnow)
    attempt_number = Column(Integer, default=1)
    status = Column(String(50), default="received")  # received, drafting, blocked, in_review, reported, approved, rejected, expired
    # Fine-grained live stage for the animated agent graph (which agent is working now):
    # queued, drafting(P1), validating(P1), diagram(P1), scanning(P2), costing(P3),
    # reliability(P4), reporting(P5), notifying(P6), gated(P7), done
    stage = Column(String(30), default="queued")
    
    submitter = relationship("UserAccount", back_populates="requests")
    blueprint = relationship("Blueprint", back_populates="request", uselist=False)
    decisions = relationship("ApprovalDecision", back_populates="request")

class Blueprint(Base):
    __tablename__ = "blueprint"
    
    blueprint_id = Column(String(50), primary_key=True)
    request_id = Column(String(50), ForeignKey("migration_request.request_id"), nullable=False, unique=True)
    attempt_number = Column(Integer, nullable=False)
    source_platform = Column(String(50), nullable=False)
    target_cloud_provider = Column(String(50), nullable=False)
    terraform_code_ref = Column(String(255), nullable=False)
    architecture_diagram_ref = Column(String(255), nullable=False)
    validated_at = Column(DateTime, nullable=False)
    drafted_at = Column(DateTime, default=datetime.utcnow)
    
    request = relationship("MigrationRequest", back_populates="blueprint")
    security_findings = relationship("SecurityFinding", back_populates="blueprint", cascade="all, delete-orphan")
    cost_estimates = relationship("CostEstimate", back_populates="blueprint", cascade="all, delete-orphan")
    reliability_findings = relationship("ReliabilityFinding", back_populates="blueprint", cascade="all, delete-orphan")
    report = relationship("ConsolidatedReport", back_populates="blueprint", uselist=False, cascade="all, delete-orphan")

class SecurityFinding(Base):
    __tablename__ = "security_finding"
    
    finding_id = Column(String(50), primary_key=True)
    blueprint_id = Column(String(50), ForeignKey("blueprint.blueprint_id"), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow)
    
    blueprint = relationship("Blueprint", back_populates="security_findings")

class CostEstimate(Base):
    __tablename__ = "cost_estimate"
    
    estimate_id = Column(String(50), primary_key=True)
    blueprint_id = Column(String(50), ForeignKey("blueprint.blueprint_id"), nullable=False)
    monthly_cost = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    rate_card_refs = Column(JSON, nullable=False)  # list of cited card item IDs
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    blueprint = relationship("Blueprint", back_populates="cost_estimates")

class ReliabilityFinding(Base):
    __tablename__ = "reliability_finding"
    
    finding_id = Column(String(50), primary_key=True)
    blueprint_id = Column(String(50), ForeignKey("blueprint.blueprint_id"), nullable=False)
    redundancy_score = Column(Integer, nullable=False)
    notes = Column(Text, nullable=False)
    validated_at = Column(DateTime, default=datetime.utcnow)
    
    blueprint = relationship("Blueprint", back_populates="reliability_findings")

class ConsolidatedReport(Base):
    __tablename__ = "consolidated_report"
    
    report_id = Column(String(50), primary_key=True)
    blueprint_id = Column(String(50), ForeignKey("blueprint.blueprint_id"), nullable=False, unique=True)
    report_pdf_ref = Column(String(255), nullable=False)
    architecture_diagram_ref = Column(String(255), nullable=False)
    compiled_at = Column(DateTime, default=datetime.utcnow)
    
    blueprint = relationship("Blueprint", back_populates="report")

class ApprovalDecision(Base):
    __tablename__ = "approval_decision"
    
    decision_id = Column(String(50), primary_key=True)
    request_id = Column(String(50), ForeignKey("migration_request.request_id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    approver_id = Column(String(50), ForeignKey("user_account.user_id"), nullable=False)
    decision = Column(String(20), nullable=False)  # approved, rejected
    rejection_notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.utcnow)
    
    request = relationship("MigrationRequest", back_populates="decisions")
    approver = relationship("UserAccount", back_populates="decisions")
