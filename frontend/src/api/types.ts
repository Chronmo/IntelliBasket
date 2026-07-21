export interface ApiMeta {
  requestId: string;
  generatedAt?: string;
  page?: number;
  pageSize?: number;
  totalCount?: number;
  totalPages?: number;
  snapshotDate?: string | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta: ApiMeta;
}

export interface BusinessOverview {
  customerCount: number;
  orderCount: number;
  productCount: number;
  itemQuantity: number;
  salesAmount: number;
  averageBasketAmount: number;
  minInvoiceTs: string;
  maxInvoiceTs: string;
}

export interface MonthlySale {
  invoiceMonth: string;
  customerCount: number;
  orderCount: number;
  productCount: number;
  itemQuantity: number;
  salesAmount: number;
  averageBasketAmount: number;
}

export interface RfmSegment {
  snapshotDate: string;
  segmentCode: string;
  segmentName: string;
  customerCount: number;
  totalMonetary: number;
  averageRecencyDays: number;
  averageFrequency: number;
  averageMonetary: number;
  customerShare: number;
  monetaryShare: number;
}

export interface RfmCustomer {
  snapshotDate: string;
  customerId: string;
  latestPurchaseTs: string;
  recencyDays: number;
  frequency: number;
  monetary: number;
  rScore: number;
  fScore: number;
  mScore: number;
  rfmScore: string;
  segmentCode: string;
  segmentName: string;
}

export interface AssociationRule {
  ruleId: string;
  segmentCode: string;
  segmentName: string;
  antecedentCodes: string;
  antecedentNames: string;
  consequentCodes: string;
  consequentNames: string;
  support: number;
  confidence: number;
  lift: number;
  coverageBasketCount: number;
  scopeBasketCount: number;
  rankScore: number;
  strategy?: string;
  reason?: string;
  dataBasis?: "REAL_AND_MODEL_AUGMENTED" | "MODEL_PREDICTION";
  sourceType?: "SEGMENT_RULE" | "GLOBAL_RULE_FALLBACK" | "MODEL_PREDICTION";
}

export interface AugmentationSummary {
  enabled: boolean;
  syntheticRowCount: number;
  syntheticOrderCount: number;
  syntheticCustomerCount: number;
  predictedSalesAmount: number;
  averageConfidence: number;
  forecastStart: string | null;
  forecastEnd: string | null;
  generationBatchId: string | null;
  generationModel: string | null;
}

export interface RuleDrift {
  segmentCode: string;
  segmentName: string | null;
  antecedentCodes: string;
  antecedentNames: string | null;
  consequentCodes: string;
  consequentNames: string | null;
  previousSupport: number | null;
  previousConfidence: number | null;
  previousLift: number | null;
  currentSupport: number | null;
  currentConfidence: number | null;
  currentLift: number | null;
  liftDelta: number | null;
  supportDelta: number | null;
  driftStatus: "NEW" | "DROPPED" | "GROWING" | "DECLINING";
}

export interface TopProduct {
  stockCode: string;
  productName: string;
  orderCount: number;
  customerCount: number;
  itemQuantity: number;
  salesAmount: number;
}
